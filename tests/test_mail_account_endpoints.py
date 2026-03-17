from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main as main_module
from app.config import get_settings
from app.db.models import AuditLog, MailAccount, MailIngestionRun
from app.ingestion.gmail_oauth import GmailOAuthError


def _set_base_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv("LOG_LEVEL", "info")
    monkeypatch.setenv("DB_URL", "sqlite:///ignored.db")
    monkeypatch.setenv("MAIL_INGESTION_ENABLED", "false")
    monkeypatch.setenv("GMAIL_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GMAIL_OAUTH_CLIENT_SECRET", "client-secret")
    get_settings.cache_clear()


def _build_test_client(monkeypatch, tmp_path):
    _set_base_env(monkeypatch)
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    MailAccount.__table__.create(engine)
    MailIngestionRun.__table__.create(engine)
    AuditLog.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(main_module, "get_session_factory", lambda: SessionLocal)
    return TestClient(main_module.app), SessionLocal


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer dev-token"}


def test_create_mail_account_applies_gmail_defaults(monkeypatch, tmp_path) -> None:
    client, _ = _build_test_client(monkeypatch, tmp_path)

    response = client.post(
        "/api/mail-accounts",
        headers=_auth_headers(),
        json={
            "provider": "gmail",
            "auth_mode": "oauth_gmail",
            "account_label": "Gmail Account",
            "imap_host": "custom.gmail.host",
            "imap_port": 1143,
            "imap_user": "user@gmail.com",
            "imap_password": "",
            "oauth_refresh_token": "refresh-token",
            "mailbox": "INBOX",
            "unseen_only": True,
            "fetch_limit": 20,
            "retry_count": 3,
            "retry_backoff_seconds": 1.5,
            "is_active": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["imap_host"] == "imap.gmail.com"
    assert payload["imap_port"] == 993
    assert payload["auth_mode"] == "oauth_gmail"


def test_create_mail_account_applies_outlook_defaults(monkeypatch, tmp_path) -> None:
    client, _ = _build_test_client(monkeypatch, tmp_path)

    response = client.post(
        "/api/mail-accounts",
        headers=_auth_headers(),
        json={
            "provider": "outlook",
            "auth_mode": "password",
            "account_label": "Outlook Account",
            "imap_host": "custom.outlook.host",
            "imap_port": 1143,
            "imap_user": "user@outlook.com",
            "imap_password": "secret",
            "oauth_refresh_token": None,
            "mailbox": "INBOX",
            "unseen_only": True,
            "fetch_limit": 20,
            "retry_count": 3,
            "retry_backoff_seconds": 1.5,
            "is_active": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["imap_host"] == "outlook.office365.com"
    assert payload["imap_port"] == 993


def test_mail_ingestion_sync_returns_not_found_for_unknown_account(monkeypatch, tmp_path) -> None:
    client, _ = _build_test_client(monkeypatch, tmp_path)

    response = client.post("/api/mail-ingestion/sync?mail_account_id=999", headers=_auth_headers())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MAIL_ACCOUNT_NOT_FOUND"


def test_mail_ingestion_sync_maps_gmail_oauth_error(monkeypatch, tmp_path) -> None:
    client, SessionLocal = _build_test_client(monkeypatch, tmp_path)
    with SessionLocal() as session:
        session.add(
            MailAccount(
                provider="gmail",
                auth_mode="oauth_gmail",
                account_label="Primary Gmail",
                imap_host="imap.gmail.com",
                imap_port=993,
                imap_user="user@gmail.com",
                imap_password="",
                oauth_refresh_token="refresh-token",
                mailbox="INBOX",
                unseen_only=True,
                fetch_limit=20,
                retry_count=3,
                retry_backoff_seconds=1.5,
                is_active=True,
            )
        )
        session.commit()
        account_id = session.query(MailAccount).first().id

    class FailingService:
        def __init__(self, *args, **kwargs):
            pass

        def run_sync(self, *args, **kwargs):
            raise GmailOAuthError("refresh denied")

    monkeypatch.setattr(main_module, "MailIngestionService", FailingService)

    response = client.post(f"/api/mail-ingestion/sync?mail_account_id={account_id}", headers=_auth_headers())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "GMAIL_OAUTH_REFRESH_FAILED"


def test_mail_ingestion_runs_cursor_pagination(monkeypatch, tmp_path) -> None:
    client, SessionLocal = _build_test_client(monkeypatch, tmp_path)
    with SessionLocal() as session:
        for idx in range(4):
            session.add(
                MailIngestionRun(
                    status="completed",
                    scanned_messages=idx + 1,
                    processed_messages=idx + 1,
                    duplicate_messages=0,
                    saved_documents=idx + 1,
                    duplicate_documents=0,
                    skipped_attachments=0,
                    failed_messages=0,
                    csv_rows_parsed=0,
                    started_at=datetime.now(UTC),
                )
            )
        session.commit()

    first_page = client.get("/api/mail-ingestion/runs?limit=2", headers=_auth_headers())
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert len(first_payload["items"]) == 2
    assert first_payload["next_cursor"] is not None

    cursor = first_payload["next_cursor"]
    second_page = client.get(f"/api/mail-ingestion/runs?limit=2&cursor={cursor}", headers=_auth_headers())
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert len(second_payload["items"]) == 2


def test_delete_mail_account(monkeypatch, tmp_path) -> None:
    client, SessionLocal = _build_test_client(monkeypatch, tmp_path)
    with SessionLocal() as session:
        session.add(
            MailAccount(
                provider="gmail",
                auth_mode="password",
                account_label="To Delete",
                imap_host="imap.gmail.com",
                imap_port=993,
                imap_user="x@gmail.com",
                imap_password="x",
                oauth_refresh_token=None,
                mailbox="INBOX",
                unseen_only=True,
                fetch_limit=20,
                retry_count=3,
                retry_backoff_seconds=1.5,
                is_active=True,
            )
        )
        session.commit()
        aid = session.query(MailAccount).first().id

    r = client.delete(f"/api/mail-accounts/{aid}", headers=_auth_headers())
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert r.json()["id"] == aid

    r2 = client.delete(f"/api/mail-accounts/{aid}", headers=_auth_headers())
    assert r2.status_code == 404
