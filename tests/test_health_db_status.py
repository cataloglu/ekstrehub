from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app import main as main_module
from app.config import get_settings


def _set_base_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv("LOG_LEVEL", "info")
    monkeypatch.setenv("DB_URL", "postgresql://user:pass@localhost:5432/ekstrehub")
    monkeypatch.setenv("MAIL_INGESTION_ENABLED", "false")
    get_settings.cache_clear()


class _BrokenSession:
    def __enter__(self):
        raise SQLAlchemyError("db down")

    def __exit__(self, exc_type, exc, tb):
        return False


def _broken_session_factory():
    return _BrokenSession()


def test_health_reports_db_unavailable_when_db_is_down(monkeypatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setattr(main_module, "get_session_factory", lambda: _broken_session_factory)
    client = TestClient(main_module.app)

    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["db_available"] is False

