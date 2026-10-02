from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.api.auth import create_token, require_admin, require_user, verify_token
from app.config.settings import Settings
from main import app


def test_admin_token_round_trip() -> None:
    token = create_token("admin", "admin")

    result = verify_token(token)
    assert result is not None
    assert result["username"] == "admin"
    assert result["role"] == "admin"


def test_user_token_round_trip() -> None:
    token = create_token("test", "user")

    result = verify_token(token)
    assert result is not None
    assert result["username"] == "test"
    assert result["role"] == "user"


def test_token_rejects_invalid_value() -> None:
    assert verify_token("not-a-token") is None


def test_require_admin_accepts_admin_token() -> None:
    token = create_token("admin", "admin")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    assert require_admin(credentials) == "admin"


def test_require_admin_rejects_user_token() -> None:
    token = create_token("test", "user")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    try:
        require_admin(credentials)
        assert False, "Expected 403"
    except Exception as exc:
        assert exc.status_code == 403


def test_require_user_accepts_admin_token() -> None:
    token = create_token("admin", "admin")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    result = require_user(credentials)
    assert result["username"] == "admin"
    assert result["role"] == "admin"


def test_require_user_accepts_user_token() -> None:
    token = create_token("test", "user")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    result = require_user(credentials)
    assert result["username"] == "test"
    assert result["role"] == "user"


def test_chat_ask_requires_admin_auth() -> None:
    client = TestClient(app)

    response = client.post("/api/v1/chat/ask", json={"raw_query": "test"})

    assert response.status_code == 401


def test_chat_ask_allows_admin() -> None:
    client = TestClient(app)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = client.post(
        "/api/v1/chat/ask",
        json={"raw_query": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_chat_ask_rejects_user_role() -> None:
    client = TestClient(app)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "test", "password": "test"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = client.post(
        "/api/v1/chat/ask",
        json={"raw_query": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_documents_require_admin_auth() -> None:
    client = TestClient(app)

    assert client.get("/api/v1/documents").status_code == 401
    assert client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", b"data", "text/plain")},
    ).status_code == 401
    assert client.delete("/api/v1/documents/doc-x").status_code == 401


def test_documents_reject_user_role() -> None:
    client = TestClient(app)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "test", "password": "test"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/documents", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", b"data", "text/plain")},
        headers=headers,
    ).status_code == 403
    assert client.delete("/api/v1/documents/doc-x", headers=headers).status_code == 403


def test_admin_login_allows_protected_endpoint() -> None:
    client = TestClient(app)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    response = client.get(
        "/api/v1/chat/records",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_login_returns_role() -> None:
    client = TestClient(app)

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert admin_login.json()["role"] == "admin"

    user_login = client.post(
        "/api/v1/auth/login",
        json={"username": "test", "password": "test"},
    )
    assert user_login.json()["role"] == "user"


def test_login_failure_no_password_in_logs(caplog) -> None:
    with caplog.at_level("WARNING", logger="orionstack.auth"):
        response = TestClient(app).post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong-secret"},
        )

    assert response.status_code == 401
    assert "wrong-secret" not in caplog.text
    assert "login_failed username=admin" in caplog.text


def test_logout_logs_username_and_role(caplog) -> None:
    token = create_token("admin", "admin")

    with caplog.at_level("INFO", logger="orionstack.auth"):
        response = TestClient(app).post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert "logout username=admin" in caplog.text


def test_me_endpoint_returns_role() -> None:
    client = TestClient(app)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "test", "password": "test"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "test"
    assert body["role"] == "user"


def test_prod_config_rejects_default_admin_credentials() -> None:
    prod_settings = Settings(app_mode="prod")

    errors = prod_settings.production_config_errors()

    assert "ORIONSTACK_ADMIN_PASSWORD must be changed for prod mode" in errors
    assert "ORIONSTACK_ADMIN_TOKEN_SECRET must be changed for prod mode" in errors
    assert "ORIONSTACK_TEST_USER_PASSWORD must be changed for prod mode" in errors


def test_prod_config_requires_long_token_secret() -> None:
    prod_settings = Settings(
        app_mode="prod",
        admin_password="not-default",
        test_user_password="not-default",
        admin_token_secret="short-secret",
    )

    assert prod_settings.production_config_errors() == [
        "ORIONSTACK_ADMIN_TOKEN_SECRET must be at least 24 characters in prod mode"
    ]


def test_prod_config_accepts_overridden_credentials() -> None:
    prod_settings = Settings(
        app_mode="prod",
        admin_password="not-default",
        test_user_password="not-default",
        admin_token_secret="a-production-grade-token-secret",
    )

    assert prod_settings.production_config_errors() == []


def test_logging_settings_defaults() -> None:
    defaults = Settings()

    assert defaults.log_level == "INFO"
    assert defaults.access_log_enabled is True


def test_logging_settings_parse_env(monkeypatch) -> None:
    monkeypatch.setenv("ORIONSTACK_LOG_LEVEL", "warning")
    monkeypatch.setenv("ORIONSTACK_ACCESS_LOG_ENABLED", "false")

    resolved = Settings()

    assert resolved.log_level == "WARNING"
    assert resolved.access_log_enabled is False


def test_user_accounts_property() -> None:
    s = Settings()

    accounts = s.user_accounts
    assert "admin" in accounts
    assert accounts["admin"] == ("admin", "admin")
    assert "test" in accounts
    assert accounts["test"] == ("test", "user")