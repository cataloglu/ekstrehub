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


def test_spa_includes_ingress_base_script(monkeypatch) -> None:
    """HA Ingress: index.html sets <base> from location.pathname (inline script in ui/index.html)."""
    _set_base_env(monkeypatch)
    client = TestClient(app)
    response = client.get("/")
    # May 404 if ui/dist not built; if 200, ingress bootstrap must be present
    if response.status_code == 200:
        assert "ingressBasePath" in response.text
        assert "document.createElement" in response.text and "base" in response.text
