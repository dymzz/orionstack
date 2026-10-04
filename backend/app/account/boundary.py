"""Verified identity -> Principal -> current server membership. No Core dependency on OIDC."""

import secrets

from fastapi import HTTPException, Request

from app.account.settings import IdentitySettings
from app.account.store import PostgresAccountStore, demo_sessions
from app.config.core_settings import CoreConfigurationError, CoreSettings
from app.knowledge.postgres import DatabaseUnavailable
from app.security.contracts import Principal, TrustedContext


def get_identity_settings():
    try:
        return IdentitySettings().validate()
    except (CoreConfigurationError,ValueError):
        raise HTTPException(503,"Identity configuration is unavailable") from None


def get_account_store():
    return demo_sessions if get_identity_settings().mode == "demo" else PostgresAccountStore()


def demo_context(username, role):
    # This path is selected only by explicit demo identity mode.
    access=CoreSettings().access_for_user(username,role)
    return TrustedContext(
        principal=Principal(tenant_id=access.tenant_id,principal_id=username,issuer="urn:orionstack:demo",subject=username,
                            display_name=username,authentication="demo"),
        access=access,policy_version="demo-membership-v1")


def require_origin(request: Request, config: IdentitySettings):
    if request.headers.get("origin") != config.public_origin:
        raise HTTPException(403,"Request origin is not allowed")


def require_session(request: Request):
    config = get_identity_settings()
    token = request.cookies.get(config.cookie_name)
    if not token or len(token) > 128:
        raise HTTPException(401,"Authentication required")
    try:
        session = get_account_store().load_session(token)
        if session and config.mode == "demo":
            # Demo configuration changes also take effect without trusting a stored role.
            from app.config.settings import settings
            username = session.context.principal.subject
            account = settings.user_accounts.get(username)
            if not account:
                session = None
            else:
                from app.account.store import Session
                session = Session(demo_context(username,account[1]),session.csrf_token,session.expires_at)
    except (CoreConfigurationError,DatabaseUnavailable,ValueError):
        raise HTTPException(503,"Identity session store is unavailable") from None
    except PermissionError:
        raise HTTPException(403,"Account has no core access binding") from None
    if session is None:
        raise HTTPException(401,"Authentication required")
    if request.method not in {"GET","HEAD","OPTIONS"}:
        require_origin(request,config)
        csrf = request.headers.get("x-csrf-token","")
        if not secrets.compare_digest(csrf.encode(),session.csrf_token.encode()):
            raise HTTPException(403,"CSRF validation failed")
    request.state.trusted_context = session.context
    return session


def session_user(request: Request):
    session = require_session(request)
    context = session.context
    return {"username":context.principal.principal_id,
            "role":"admin" if "admin" in context.access.roles else "user",
            "trusted_context":context}
