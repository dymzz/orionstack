"""Local HTTP acceptance using an owned synthetic fixture; never uploads existing files."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "backend"))


def validate():
    from app.config.settings import settings
    from app.account.settings import IdentitySettings
    identity_settings = IdentitySettings().validate()
    if identity_settings.mode != "demo": raise RuntimeError("Local demo identity mode is required")
    accounts = settings.user_accounts
    curator = next(((name,password) for name,(password,role) in accounts.items() if role == "admin"),None)
    reader = next(((name,password) for name,(password,role) in accounts.items() if role == "user"),None)
    if curator is None or reader is None: raise RuntimeError("A configured curator and reader are required")
    identity = "p1-validation-" + uuid4().hex
    text = b"Synthetic IT demonstration: password reset uses the sample IT portal. No leave policy is provided."
    replacement = b"Synthetic IT demonstration v2: password reset uses the updated sample IT portal."
    report = {"created_at":datetime.now(timezone.utc).isoformat(),"fixture_document_id":identity,"checks":[]}
    def check(name, condition):
        if not condition: raise RuntimeError("Acceptance failed: " + name)
        report["checks"].append(name)
    # Loopback traffic must not be forwarded to the process's external HTTP proxy.
    with httpx.Client(base_url="http://127.0.0.1:8000",timeout=180,trust_env=False) as client:
        def authenticate(account):
            response = client.post("/api/auth/demo-login",headers={"Origin":identity_settings.public_origin},
                                   json={"username":account[0],"password":account[1]})
            if response.status_code != 200: raise RuntimeError("Configured account login failed")
            check("session_cookie_is_http_only", "HttpOnly" in response.headers.get("set-cookie", ""))
            session = client.get("/api/auth/session")
            if session.status_code != 200: raise RuntimeError("Configured account login failed")
            headers = {"Cookie":identity_settings.cookie_name+"="+response.cookies[identity_settings.cookie_name],
                       "X-CSRF-Token":session.json()["csrf_token"],"Origin":identity_settings.public_origin}
            client.cookies.clear()
            return headers
        admin_headers, user_headers = authenticate(curator), authenticate(reader)
        attempted = False
        try:
            check("unauthenticated_core_denied",client.get("/api/access-context").status_code == 401)
            access = client.get("/api/access-context",headers=user_headers)
            check("reader_can_query_cannot_maintain",access.status_code == 200 and access.json()["permissions"]["query"]
                  and not access.json()["permissions"]["documents_maintain"])
            check("missing_csrf_denied",client.post("/api/query",headers={k:v for k,v in user_headers.items() if k!="X-CSRF-Token"},
                  json={"query":"fixed synthetic test"}).status_code == 403)
            check("wrong_origin_denied",client.post("/api/query",headers={**user_headers,"Origin":"https://attacker.example.test"},
                  json={"query":"fixed synthetic test"}).status_code == 403)
            denied = client.post("/api/documents",headers=user_headers,files={"file":("p1-test.txt",text)},data={"document_id":identity})
            check("reader_upload_denied",denied.status_code == 403)
            attempted = True
            created = client.post("/api/documents",headers=admin_headers,files={"file":("p1-test.txt",text)},data={"document_id":identity})
            check("curator_upload_activates",created.status_code == 200 and created.json()["status"] == "active")
            version = created.json()["document_version"]
            original = client.get(f"/api/documents/{identity}/content",headers=user_headers,params={"document_version":version})
            check("reader_download_is_byte_exact",original.status_code == 200 and original.content == text)
            # The answer provider receives only this fixed synthetic IT text.
            negative = client.post("/api/query",headers=user_headers,json={"query":"病假需要提交什么材料？","document_ids":[identity]})
            check("irrelevant_it_evidence_is_insufficient",negative.status_code == 200 and
                  negative.json()["status"] == "insufficient_evidence" and not negative.json()["citations"])
            result = negative.json()
            check("only_owned_fixture_evidence_returned",bool(result["evidence_bundle"]["items"]) and
                  all(item["source"]["document_id"] == identity for item in result["evidence_bundle"]["items"]))
            check("provenance_pass_does_not_mean_answerable",all(item["chain"]["status"] == "pass" for item in result["evidence_bundle"]["items"]))
            report["negative_request_id"] = result["request_id"]
            report["negative_event_id"] = result["retrieval_event_id"]
            changed = client.post("/api/documents",headers=admin_headers,files={"file":("p1-test.txt",replacement)},data={"document_id":identity})
            check("replacement_has_new_active_version",changed.status_code == 200 and changed.json()["status"] == "active"
                  and changed.json()["document_version"] != version)
            check("superseded_download_denied",client.get(f"/api/documents/{identity}/content",headers=user_headers,
                  params={"document_version":version}).status_code == 404)
            stale = client.post(f"/api/documents/{identity}/index",headers=admin_headers,data={"document_version":version})
            check("stale_index_version_rejected",stale.status_code in (404,409))
            indexed = client.post(f"/api/documents/{identity}/index",headers=admin_headers,
                data={"document_version":changed.json()["document_version"]})
            check("same_version_index_is_idempotent",indexed.status_code == 200 and indexed.json()["embedded_chunks"] == 0)
            check("reader_revoke_denied",client.delete(f"/api/documents/{identity}",headers=user_headers).status_code == 403)
        finally:
            if attempted:
                cleanup = client.delete(f"/api/documents/{identity}",headers=admin_headers)
                report["cleanup_status"] = cleanup.status_code
                if cleanup.status_code not in (200,404): raise RuntimeError("Owned fixture cleanup failed")
        listed = client.get("/api/documents",headers=user_headers)
        check("revoked_fixture_leaves_active_catalog",listed.status_code == 200 and
              all(item["document_id"] != identity for item in listed.json()["items"]))
        check("server_logout_revokes_session",client.post("/api/auth/logout",headers=user_headers).status_code == 200)
        check("revoked_session_cannot_read",client.get("/api/access-context",headers=user_headers).status_code == 401)
        client.post("/api/auth/logout",headers=admin_headers)
    report["status"] = "passed"
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--live",action="store_true")
    parser.add_argument("--report",type=Path,default=ROOT / ".runtime/p1-0-1/http-acceptance.json")
    args = parser.parse_args()
    if not args.live:
        print("Preview: localhost HTTP, fixed synthetic fixture, local embedding and synthetic-only answer call; --live executes")
    else:
        try: result = validate()
        except Exception as error:
            message = str(error) if isinstance(error,RuntimeError) and (str(error).startswith("Acceptance failed: ")
                or str(error) in ("Configured account login failed","A configured curator and reader are required","Owned fixture cleanup failed")) else type(error).__name__
            print(f"HTTP acceptance failed: {message}",file=sys.stderr)
            raise SystemExit(1) from None
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"HTTP acceptance passed: {len(result['checks'])} checks; owned fixture revoked")
