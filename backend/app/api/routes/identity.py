"""Browser BFF login boundary. Browser receives only opaque HttpOnly session + CSRF."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.account.boundary import (demo_context, get_account_store, get_identity_settings,
                                  require_origin, require_session)
from app.account.oidc import OidcClient, IdentityProviderUnavailable, InvalidIdentityResponse
from app.config.core_settings import CoreConfigurationError
from app.knowledge.postgres import DatabaseUnavailable
from app.observability.logging import get_logger
from app.schemas.auth import LoginRequest

router = APIRouter(prefix="/api/auth",tags=["account-session"])
logger = get_logger("orionstack.identity")


def get_oidc_client():
    return OidcClient(get_identity_settings())


def safe_return_path(value):
    # Reject backslash/control-character browser URL normalization and protocol-relative redirects.
    if not value.startswith("/") or value.startswith("//") or "\\" in value or any(ord(ch)<32 for ch in value):
        raise HTTPException(400,"Invalid return path")
    return value


def cookie(response, name, value, lifetime, config):
    response.set_cookie(name,value,max_age=lifetime,httponly=True,secure=config.secure_cookie,
                        samesite="lax",path="/")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


def start_session(context, request, response, config, store):
    # Rotate rather than promote a caller's previous session ID.
    previous = request.cookies.get(config.cookie_name)
    if previous:
        store.revoke_session(previous)
    token,session = store.create_session(context,config.session_seconds)
    cookie(response,config.cookie_name,token,config.session_seconds,config)
    logger.info("session_created principal_id=%s authentication=%s",context.principal.principal_id,context.principal.authentication)
    return session


@router.get("/config")
def config():
    settings = get_identity_settings()
    return JSONResponse({"mode":settings.mode,"login_url":"/api/auth/start" if settings.mode=="oidc" else None},headers={"Cache-Control":"no-store"})


@router.get("/start")
def start_login(request: Request, return_to: str = "/", client=Depends(get_oidc_client), store=Depends(get_account_store)):
    config = get_identity_settings()
    if config.mode != "oidc":
        raise HTTPException(404,"OIDC is not selected")
    try:
        url,browser = client.authorize(safe_return_path(return_to),store)
    except (IdentityProviderUnavailable,InvalidIdentityResponse,CoreConfigurationError,DatabaseUnavailable):
        raise HTTPException(503,"OIDC login is unavailable") from None
    response = RedirectResponse(url,status_code=302)
    cookie(response,config.flow_cookie_name,browser,300,config)
    return response


@router.get("/callback")
def callback(request: Request, client=Depends(get_oidc_client), store=Depends(get_account_store)):
    config = get_identity_settings()
    if config.mode != "oidc":
        raise HTTPException(404,"OIDC is not selected")
    # Duplicate parameters, denied consent and unknown transactions all fail closed.
    query = request.query_params
    browser = request.cookies.get(config.flow_cookie_name)
    if (not browser or len(query.getlist("state")) != 1 or not query.get("state")
            or query.get("iss",config.issuer) != config.issuer):
        raise HTTPException(400,"Invalid OIDC callback")
    try:
        flow = store.consume_flow(query["state"],browser)
        if not flow or query.get("error") or len(query.getlist("code")) != 1 or not query.get("code"):
            raise InvalidIdentityResponse("Invalid or expired transaction")
        issuer,subject,display = client.exchange(query["code"],flow)
        context = store.bind_identity(issuer,subject,display)
        response = RedirectResponse(config.public_origin+safe_return_path(flow.return_path),status_code=303)
        start_session(context,request,response,config,store)
        response.delete_cookie(config.flow_cookie_name,path="/",secure=config.secure_cookie,httponly=True,samesite="lax")
        return response
    except InvalidIdentityResponse:
        raise HTTPException(400,"Invalid OIDC callback") from None
    except PermissionError:
        raise HTTPException(403,"Identity verified; local membership is not available") from None
    except (IdentityProviderUnavailable,CoreConfigurationError,DatabaseUnavailable):
        raise HTTPException(503,"Identity service is unavailable") from None


@router.post("/demo-login")
def demo_login(payload: LoginRequest, request: Request, store=Depends(get_account_store)):
    config = get_identity_settings()
    if config.mode != "demo":
        raise HTTPException(404,"Demo login is disabled")
    require_origin(request,config)
    from app.api.auth import authenticate_user
    valid,role = authenticate_user(payload.username,payload.password)
    if not valid:
        raise HTTPException(401,"Invalid username or password")
    try:
        context = demo_context(payload.username,role)
    except PermissionError:
        raise HTTPException(403,"Account has no core access binding") from None
    except (CoreConfigurationError,ValueError):
        raise HTTPException(503,"Core access configuration is unavailable") from None
    response = JSONResponse({"authenticated":True})
    start_session(context,request,response,config,store)
    return response


@router.get("/session")
def session_status(request: Request):
    session = require_session(request)
    principal = session.context.principal
    return JSONResponse({"authenticated":True,"principal_id":principal.principal_id,
        "username":principal.display_name,"role":"admin" if "admin" in session.context.access.roles else "user",
        "authentication":principal.authentication,"csrf_token":session.csrf_token,
        "expires_at":session.expires_at.isoformat()},headers={"Cache-Control":"no-store"})


@router.post("/logout")
def logout(request: Request, store=Depends(get_account_store)):
    session = require_session(request)
    config = get_identity_settings()
    try:
        store.revoke_session(request.cookies[config.cookie_name])
    except DatabaseUnavailable:
        raise HTTPException(503,"Session revocation is unavailable") from None
    logger.info("session_revoked principal_id=%s",session.context.principal.principal_id)
    response = JSONResponse({"status":"logged_out"},headers={"Cache-Control":"no-store"})
    response.delete_cookie(config.cookie_name,path="/",secure=config.secure_cookie,httponly=True,samesite="lax")
    return response
