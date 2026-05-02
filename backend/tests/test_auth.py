from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.api.auth import create_admin_token, require_admin, verify_admin_token
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
