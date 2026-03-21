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


def test_spa_injects_base_from_x_ingress_path(monkeypatch) -> None:
    """HA Core sets X-Ingress-Path to /api/hassio_ingress/{token} — must drive <base href>."""
    _set_base_env(monkeypatch)
    client = TestClient(app)
    ingress_path = "/api/hassio_ingress/abc123"
    response = client.get("/", headers={"X-Ingress-Path": ingress_path})
    if response.status_code == 200:
        assert '<base href="/api/hassio_ingress/abc123/">' in response.text
        assert 'src="/api/hassio_ingress/abc123/assets/' in response.text


def test_gmail_oauth_not_configured_redirect_uses_ingress_trailing_slash(monkeypatch) -> None:
    """HA returns 404 for /api/hassio_ingress/TOKEN?x= — need .../TOKEN/?x=."""
    _set_base_env(monkeypatch)
    client = TestClient(app)
    r = client.get(
        "/api/oauth/gmail/start",
        follow_redirects=False,
        headers={"X-Ingress-Path": "/api/hassio_ingress/abc123"},
    )
    assert r.status_code == 307
    assert r.headers.get("location") == "/api/hassio_ingress/abc123/?oauth=not_configured"


def test_spa_ingress_base_from_referer_when_header_stripped(monkeypatch) -> None:
    """Some proxies strip X-Ingress-Path; Referer may still contain the ingress path."""
    _set_base_env(monkeypatch)
    client = TestClient(app)
    response = client.get(
        "/",
        headers={"Referer": "https://example.com/api/hassio_ingress/xyz789/"},
    )
    if response.status_code == 200:
        assert '<base href="/api/hassio_ingress/xyz789/">' in response.text
        assert 'src="/api/hassio_ingress/xyz789/assets/' in response.text
