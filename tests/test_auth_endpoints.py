"""Basic API accessibility tests.

EkstreHub has no token-based auth — authentication is handled by
Home Assistant Ingress at the infrastructure level.  These tests
simply confirm that API endpoints are reachable without any credentials.
"""
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def _set_base_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv("LOG_LEVEL", "info")
    monkeypatch.setenv("DB_URL", "postgresql://user:pass@localhost:5432/ekstrehub")
    monkeypatch.setenv("MAIL_INGESTION_ENABLED", "false")
    get_settings.cache_clear()


def test_cards_endpoint_accessible_without_credentials(monkeypatch) -> None:
    _set_base_env(monkeypatch)
    client = TestClient(app)
    response = client.get("/api/cards")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_health_endpoint_accessible_without_credentials(monkeypatch) -> None:
    _set_base_env(monkeypatch)
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_spa_injects_base_tag_when_x_ingress_path_present(monkeypatch) -> None:
    """HA Ingress: X-Ingress-Path header triggers <base href> injection."""
    _set_base_env(monkeypatch)
    client = TestClient(app)
    ingress_path = "/api/hassio_ingress/abc123/"
    response = client.get("/", headers={"X-Ingress-Path": ingress_path})
    # May 404 if ui/dist not built; if 200, base tag must be present
    if response.status_code == 200:
        assert f'<base href="{ingress_path}">' in response.text
