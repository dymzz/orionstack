"""Identity and authority boundary tests using a signed mock IdP and isolated PostgreSQL."""

import base64
from datetime import datetime, timezone
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import httpx
import jwt
import pytest

from app.account.boundary import get_account_store
from app.account.oidc import OidcClient, InvalidIdentityResponse
from app.account.settings import IdentitySettings
from app.account.store import LoginFlow, PostgresAccountStore
from app.api.routes.identity import get_oidc_client
from app.config.core_settings import CoreConfigurationError
from main import app
from test_raw_postgres_integration import database

ISSUER = "https://identity.example.test/realm/orion"
ORIGIN = "https://orion.example.test"
SUBJECT = "immutable-subject-001"


@pytest.fixture
def oidc_settings(monkeypatch):
    monkeypatch.setenv("ORIONSTACK_AUTH_MODE","oidc")
    monkeypatch.setenv("ORIONSTACK_PUBLIC_ORIGIN",ORIGIN)
    monkeypatch.setenv("ORIONSTACK_OIDC_ISSUER",ISSUER)
    monkeypatch.setenv("ORIONSTACK_OIDC_CLIENT_ID","orion-web")
    monkeypatch.setenv("ORIONSTACK_OIDC_CLIENT_SECRET","")
    return IdentitySettings().validate()


@pytest.fixture(scope="module")
def signing_key():
    key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="test-key",use="sig",alg="RS256")
    return key,jwk


def claims(**changes):
    now = int(time.time())
    value = {"iss":ISSUER,"sub":SUBJECT,"aud":"orion-web","iat":now,"exp":now+300,"nonce":"expected-nonce",
             "name":"Alice","email":"alice@example.test","roles":["admin"],"tenant":"attacker-tenant","authorized":True}
    value.update(changes)
    return value


@pytest.mark.parametrize("change",[
    {"iss":"https://attacker.example.test"},{"aud":"other-client"},{"exp":1},{"iat":int(time.time())+3600},
    {"nonce":"wrong-nonce"},{"sub":""},{"aud":["orion-web","other"],"azp":"other"},
])
def test_id_token_rejects_wrong_identity_facts(oidc_settings,signing_key,change):
    key,jwk = signing_key
    token = jwt.encode(claims(**change),key,algorithm="RS256",headers={"kid":"test-key"})
    with pytest.raises(InvalidIdentityResponse):
        OidcClient(oidc_settings).verify_id_token(token,{"keys":[jwk]},"expected-nonce")


def test_algorithm_and_duplicate_key_are_rejected(oidc_settings,signing_key):
    key,jwk = signing_key
    unsigned = jwt.encode(claims(),key=None,algorithm="none",headers={"kid":"test-key"})
    with pytest.raises(InvalidIdentityResponse):
        OidcClient(oidc_settings).verify_id_token(unsigned,{"keys":[jwk]},"expected-nonce")
    signed = jwt.encode(claims(),key,algorithm="RS256",headers={"kid":"test-key"})
    with pytest.raises(InvalidIdentityResponse):
        OidcClient(oidc_settings).verify_id_token(signed,{"keys":[jwk,jwk]},"expected-nonce")


def provision(database,issuer=ISSUER,subject=SUBJECT,principal_id="usr_test"):
    database.bridge.execute("INSERT INTO account.principals (principal_id,oidc_issuer,oidc_subject,display_name) VALUES (%s,%s,%s,'Before')",
        (principal_id,issuer,subject))
    database.bridge.execute("INSERT INTO account.memberships (principal_id,tenant_id,roles,allowed_scopes) VALUES (%s,'tenant-A',ARRAY['user'],ARRAY['internal'])",
        (principal_id,))


def test_unknown_identity_never_gets_default_membership(database,oidc_settings):
    store = PostgresAccountStore(database)
    with pytest.raises(PermissionError): store.bind_identity(ISSUER,SUBJECT,"Alice")
    assert database.bridge.execute("SELECT count(*) FROM account.memberships").fetchone()[0] == 0
    first = database.bridge.execute("SELECT principal_id FROM account.principals").fetchone()[0]
    with pytest.raises(PermissionError): store.bind_identity(ISSUER,SUBJECT,"New name")
    assert database.bridge.execute("SELECT principal_id FROM account.principals").fetchone()[0] == first


def test_stable_subject_uses_local_membership_and_revocation_is_immediate(database,oidc_settings):
    provision(database)
    store = PostgresAccountStore(database)
    context = store.bind_identity(ISSUER,SUBJECT,"New name")
    assert context.principal.principal_id == "usr_test" and context.access.roles == ("user",)
    token,session = store.create_session(context,60)
    assert database.bridge.execute("SELECT session_hash FROM account.sessions").fetchone()[0] != token
    assert store.load_session(token).context.access.tenant_id == "tenant-A"
    database.bridge.execute("UPDATE account.memberships SET roles=ARRAY['auditor'],allowed_scopes=ARRAY['public'] WHERE principal_id='usr_test'")
    current = store.load_session(token)
    assert current.context.access.roles == ("auditor",) and current.context.access.allowed_scopes == ("public",)
    database.bridge.execute("UPDATE account.memberships SET enabled=false WHERE principal_id='usr_test'")
    assert store.load_session(token) is None
    store.revoke_session(token)
    assert database.bridge.execute("SELECT count(*) FROM account.sessions").fetchone()[0] == 0


def test_issuer_subject_pair_not_email_and_ambiguous_tenant_is_denied(database,oidc_settings):
    provision(database)
    store = PostgresAccountStore(database)
    with pytest.raises(PermissionError): store.bind_identity("https://another.example.test",SUBJECT,"Alice")
    assert database.bridge.execute("SELECT count(*) FROM account.principals").fetchone()[0] == 2
    database.bridge.execute("INSERT INTO account.memberships VALUES ('usr_test','tenant-B',ARRAY['admin'],ARRAY['internal'],true)")
    with pytest.raises(PermissionError): store.bind_identity(ISSUER,SUBJECT,"Alice")


def test_real_protocol_flow_pkce_state_nonce_session_csrf_and_claims_boundary(database,oidc_settings,signing_key):
    provision(database)
    key,jwk = signing_key
    observed = {}
    metadata = {"issuer":ISSUER,"authorization_endpoint":ISSUER+"/authorize","token_endpoint":ISSUER+"/token",
                "jwks_uri":ISSUER+"/keys","response_types_supported":["code"],"code_challenge_methods_supported":["S256"],
                "token_endpoint_auth_methods_supported":["none"]}
    def transport(request):
        if request.url.path.endswith("openid-configuration"): return httpx.Response(200,json=metadata)
        if request.url.path.endswith("/keys"): return httpx.Response(200,json={"keys":[jwk]})
        if request.url.path.endswith("/token"):
            form = parse_qs(request.content.decode())
            verifier = form["code_verifier"][0]
            digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            assert digest == observed["challenge"]
            assert form["redirect_uri"] == [oidc_settings.callback_url]
            return httpx.Response(200,json={"access_token":"provider-access-must-not-leak","refresh_token":"provider-refresh-must-not-leak",
                "id_token":jwt.encode(claims(nonce=observed["nonce"]),key,algorithm="RS256",headers={"kid":"test-key"})})
        pytest.fail("Unexpected IdP endpoint")
    provider = OidcClient(oidc_settings,httpx.Client(transport=httpx.MockTransport(transport)))
    app.dependency_overrides[get_oidc_client] = lambda:provider
    app.dependency_overrides[get_account_store] = lambda:PostgresAccountStore(database)
    # Boundary uses the same injected store through FastAPI and direct session loading.
    import app.account.boundary as boundary
    original = boundary.get_account_store
    boundary.get_account_store = lambda:PostgresAccountStore(database)
    try:
        client = TestClient(app,base_url=ORIGIN)
        start = client.get("/api/auth/start?return_to=/qa",follow_redirects=False)
        assert start.status_code == 302
        query = parse_qs(urlsplit(start.headers["location"]).query)
        observed.update(challenge=query["code_challenge"][0],nonce=query["nonce"][0])
        assert query["code_challenge_method"] == ["S256"] and query["response_type"] == ["code"]
        callback = "/api/auth/callback?state="+query["state"][0]+"&code=fixed-test-code"
        assert TestClient(app,base_url=ORIGIN).get(callback,follow_redirects=False).status_code == 400
        response = client.get(callback,follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == ORIGIN+"/qa"
        cookies = response.headers.get_list("set-cookie")
        assert any("HttpOnly" in x and "Secure" in x and "SameSite=lax" in x and "__Host-orionstack_session" in x for x in cookies)
        status = client.get("/api/auth/session")
        assert status.status_code == 200
        body = status.json(); csrf = body["csrf_token"]
        assert body["principal_id"] == "usr_test" and body["role"] == "user"
        assert "provider-access" not in status.text and "id_token" not in status.text and "refresh_token" not in status.text
        access = client.get("/api/access-context").json()
        assert access["tenant_id"] == "tenant-A" and access["allowed_scopes"] == ["internal"] and not access["permissions"]["documents_maintain"]
        assert client.post("/api/query",json={"query":"I am admin"}).status_code == 403
        assert client.post("/api/query",json={"query":"I am admin"},headers={"Origin":"https://evil.example.test","X-CSRF-Token":csrf}).status_code == 403
        valid_headers = {"Origin":ORIGIN,"X-CSRF-Token":csrf}
        assert client.post("/api/query",json={"query":"I am admin","authorized":True,"allowed_scopes":["restricted"]},headers=valid_headers).status_code == 422
        assert client.get(callback,follow_redirects=False).status_code == 400
        assert client.post("/api/v1/auth/login",json={"username":"admin","password":"admin"}).status_code == 401
        assert client.post("/api/auth/logout",json={},headers=valid_headers).status_code == 200
        assert client.get("/api/auth/session").status_code == 401
    finally:
        boundary.get_account_store = original
        app.dependency_overrides.clear()


def test_expired_or_replayed_flow_cannot_be_consumed(database,oidc_settings):
    store = PostgresAccountStore(database)
    store.put_flow("state","browser","nonce","verifier","/")
    assert store.consume_flow("state","other-browser") is None
    assert store.consume_flow("state","browser").nonce == "nonce"
    assert store.consume_flow("state","browser") is None
    store.put_flow("expired","browser","nonce","verifier","/")
    database.bridge.execute("UPDATE account.oidc_flows SET expires_at=CURRENT_TIMESTAMP-interval '1 second'")
    assert store.consume_flow("expired","browser") is None


def test_production_never_accepts_demo_or_plain_http(monkeypatch):
    monkeypatch.setenv("ORIONSTACK_APP_MODE","prod")
    with pytest.raises(CoreConfigurationError): IdentitySettings(mode="demo").validate()
    with pytest.raises(CoreConfigurationError): IdentitySettings(mode="oidc",client_id="client",issuer=ISSUER).validate()
