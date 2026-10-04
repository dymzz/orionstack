"""OIDC protocol adapter. No claim-to-permission mapping and no tokens sent to the UI."""

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
import jwt

from app.config.core_settings import CoreConfigurationError


class IdentityProviderUnavailable(RuntimeError):
    pass


class InvalidIdentityResponse(ValueError):
    pass


class OidcClient:
    def __init__(self, settings, client=None):
        self.settings = settings.validate()
        self.client = client

    def request_json(self, method, url, **kwargs):
        try:
            if self.client is not None:
                response = self.client.request(method,url,**kwargs)
            else:
                with httpx.Client(timeout=15,follow_redirects=False) as client:
                    response = client.request(method,url,**kwargs)
            if response.status_code != 200 or len(response.content) > 1024*1024:
                raise IdentityProviderUnavailable("OIDC provider response is unavailable")
            value = response.json()
            if not isinstance(value,dict):
                raise ValueError
            return value
        except (httpx.HTTPError,ValueError):
            raise IdentityProviderUnavailable("OIDC provider response is unavailable") from None

    def metadata(self):
        data = self.request_json("GET",self.settings.issuer.rstrip("/")+"/.well-known/openid-configuration")
        if data.get("issuer") != self.settings.issuer:
            raise InvalidIdentityResponse("Discovery issuer mismatch")
        for name in ("authorization_endpoint","token_endpoint","jwks_uri"):
            self.settings.validate_provider_url(data.get(name,""))
        if "code" not in data.get("response_types_supported",[]):
            raise InvalidIdentityResponse("Authorization Code is required")
        if "code_challenge_methods_supported" in data and "S256" not in data["code_challenge_methods_supported"]:
            raise InvalidIdentityResponse("PKCE S256 is required")
        return data

    def authorize(self, return_path, store):
        metadata = self.metadata()
        state,browser,nonce,verifier = (secrets.token_urlsafe(32) for _ in range(4))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode().rstrip("=")
        store.put_flow(state,browser,nonce,verifier,return_path)
        query = urlencode({"client_id":self.settings.client_id,"redirect_uri":self.settings.callback_url,
            "response_type":"code","scope":"openid profile","state":state,"nonce":nonce,
            "code_challenge":challenge,"code_challenge_method":"S256","response_mode":"query"})
        sep = "&" if "?" in metadata["authorization_endpoint"] else "?"
        return metadata["authorization_endpoint"]+sep+query,browser

    def exchange(self, code, flow):
        metadata = self.metadata()
        data = {"grant_type":"authorization_code","code":code,"redirect_uri":self.settings.callback_url,
                "client_id":self.settings.client_id,"code_verifier":flow.code_verifier}
        kwargs = {}
        if self.settings.client_secret:
            if "client_secret_basic" not in metadata.get("token_endpoint_auth_methods_supported",["client_secret_basic"]):
                raise CoreConfigurationError("OIDC adapter requires client_secret_basic for confidential clients")
            kwargs["auth"] = (self.settings.client_id,self.settings.client_secret)
        elif "none" not in metadata.get("token_endpoint_auth_methods_supported",[]):
            raise CoreConfigurationError("OIDC client secret is required by this provider")
        token_response = self.request_json("POST",metadata["token_endpoint"],data=data,**kwargs)
        encoded = token_response.get("id_token")
        if not isinstance(encoded,str):
            raise InvalidIdentityResponse("Missing ID token")
        jwks = self.request_json("GET",metadata["jwks_uri"])
        return self.verify_id_token(encoded,jwks,flow.nonce)

    def verify_id_token(self, encoded, jwks, nonce):
        try:
            header = jwt.get_unverified_header(encoded)
            # Fixed allowlist: neither algorithm nor arbitrary key URL comes from the token.
            algorithm = header.get("alg")
            if algorithm not in {"RS256","ES256"} or not isinstance(header.get("kid"),str):
                raise ValueError
            keys = [key for key in jwks["keys"] if key.get("kid") == header["kid"]
                    and key.get("use","sig") == "sig" and key.get("alg",algorithm) == algorithm
                    and ("key_ops" not in key or "verify" in key["key_ops"])]
            if len(keys) != 1:
                raise ValueError
            key = jwt.PyJWK.from_dict(keys[0],algorithm=algorithm).key
            claims = jwt.decode(encoded,key,algorithms=[algorithm],audience=self.settings.client_id,
                issuer=self.settings.issuer,leeway=30,options={"require":["iss","sub","aud","exp","iat","nonce"]})
            if not isinstance(claims["sub"],str) or not claims["sub"].strip():
                raise ValueError
            if not isinstance(claims["nonce"],str) or not secrets.compare_digest(claims["nonce"],nonce):
                raise ValueError
            if (isinstance(claims["aud"],list) and len(claims["aud"]) > 1 and claims.get("azp") != self.settings.client_id
                    or "azp" in claims and claims["azp"] != self.settings.client_id):
                raise ValueError
            # Verified claims establish identity only. Ignore tenant, roles, groups, scopes, admin flags.
            display = claims.get("name")
            return claims["iss"],claims["sub"],display if isinstance(display,str) and display.strip() else claims["sub"]
        except (jwt.PyJWTError,KeyError,TypeError,ValueError):
            raise InvalidIdentityResponse("Invalid OIDC identity response") from None
