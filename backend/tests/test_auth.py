from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.api.auth import create_admin_token, require_admin, verify_admin_token
from app.config.settings import Settings
from main import app


def test_admin_token_round_trip() -> None:
    token = create_admin_token("admin")

    assert verify_admin_token(token) == "admin"


def test_admin_token_rejects_invalid_value() -> None:
    assert verify_admin_token("not-a-token") is None


def test_require_admin_accepts_bearer_token() -> None:
    token = create_admin_token("admin")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    assert require_admin(credentials) == "admin"


def test_admin_endpoint_requires_auth() -> None:
    client = TestClient(app)

    response = client.get("/api/chat/records")

    assert response.status_code == 401


def test_admin_login_allows_protected_endpoint() -> None:
    client = TestClient(app)

    login_response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    response = client.get(
        "/api/chat/records",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "items" in response.json()


def test_prod_config_rejects_default_admin_credentials() -> None:
    prod_settings = Settings(app_mode="prod")

    errors = prod_settings.production_config_errors()

    assert "ORIONSTACK_ADMIN_PASSWORD must be changed for prod mode" in errors
    assert "ORIONSTACK_ADMIN_TOKEN_SECRET must be changed for prod mode" in errors


def test_prod_config_requires_long_token_secret() -> None:
    prod_settings = Settings(
        app_mode="prod",
        admin_password="not-default",
        admin_token_secret="short-secret",
    )

    assert prod_settings.production_config_errors() == [
        "ORIONSTACK_ADMIN_TOKEN_SECRET must be at least 24 characters in prod mode"
    ]


def test_prod_config_accepts_overridden_admin_credentials() -> None:
    prod_settings = Settings(
        app_mode="prod",
        admin_password="not-default",
        admin_token_secret="a-production-grade-token-secret",
    )

    assert prod_settings.production_config_errors() == []
