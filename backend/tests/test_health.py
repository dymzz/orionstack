from fastapi.testclient import TestClient

from app.api.routes import health as health_route
from app.config.settings import Settings
from main import app


def test_healthz_reports_process_alive() -> None:
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_simplified_response(monkeypatch) -> None:
    monkeypatch.setattr(health_route, "settings", Settings(search_backend="local"))
    client = TestClient(app)

    response = client.get("/readyz")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ready"
    assert "search_backend" not in body
    assert "config" not in body
    assert "elasticsearch" not in body


def test_readyz_not_ready_simplified(monkeypatch) -> None:
    monkeypatch.setattr(health_route, "settings", Settings(app_mode="prod"))
    client = TestClient(app)

    response = client.get("/readyz")
    body = response.json()

    assert response.status_code == 503
    assert body["status"] == "not_ready"
    assert "config" not in body


def test_readyz_detail_reports_ready_for_local_backend(monkeypatch) -> None:
    monkeypatch.setattr(health_route, "settings", Settings(search_backend="local"))
    client = TestClient(app)

    response = client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin",
    })
    token = response.json()["access_token"]

    response = client.get("/readyz/detail", headers={"Authorization": f"Bearer {token}"})
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["search_backend"] == "local"
    assert body["config"]["production_safe"] is True
    assert body["elasticsearch"]["enabled"] is False


def test_readyz_detail_reports_not_ready_when_elastic_indexing_failed(monkeypatch) -> None:
    monkeypatch.setattr(
        health_route,
        "settings",
        Settings(search_backend="elasticsearch", elastic_index="knowledge_units_test"),
    )
    client = TestClient(app)
    app.state.elastic_indexing_error = "Elasticsearch not reachable"
    app.state.elastic_indexed_count = 0

    response = client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin",
    })
    token = response.json()["access_token"]

    response = client.get("/readyz/detail", headers={"Authorization": f"Bearer {token}"})
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "not_ready"
    assert body["elasticsearch"] == {
        "enabled": True,
        "index_name": "knowledge_units_test",
        "indexed_count": 0,
        "indexing_error": "Elasticsearch not reachable",
        "errors": ["Elasticsearch not reachable"],
    }


def test_readyz_detail_requires_auth() -> None:
    client = TestClient(app)

    response = client.get("/readyz/detail")

    assert response.status_code in {401, 403}


def test_readyz_detail_reports_not_ready_for_unsafe_prod_config(monkeypatch) -> None:
    monkeypatch.setattr(health_route, "settings", Settings(app_mode="prod"))
    client = TestClient(app)

    response = client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin",
    })
    token = response.json()["access_token"]

    response = client.get("/readyz/detail", headers={"Authorization": f"Bearer {token}"})
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "not_ready"
    assert body["config"]["production_safe"] is False
    assert "ORIONSTACK_ADMIN_PASSWORD must be changed for prod mode" in body["config"]["errors"]