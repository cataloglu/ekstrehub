from app.ingestion.mail_client import IMAPMailClient
from app.ingestion.runtime_config import ImapRuntimeConfig


def _settings() -> ImapRuntimeConfig:
    return ImapRuntimeConfig(
        imap_host="imap.example.com",
        imap_port=993,
        imap_user="user@example.com",
        imap_password="pass",
        auth_mode="password",
        gmail_access_token=None,
        imap_mailbox="INBOX",
        imap_unseen_only=True,
        imap_fetch_limit=20,
        imap_retry_count=3,
        imap_retry_backoff_seconds=0.1,
    )


def test_fetch_messages_retries_then_succeeds(monkeypatch) -> None:
    client = IMAPMailClient(_settings())
    attempts = {"count": 0}

    def flaky_fetch():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise OSError("temporary network issue")
        return []

    monkeypatch.setattr(client, "_fetch_messages_once", flaky_fetch)
    monkeypatch.setattr("app.ingestion.mail_client.sleep", lambda _: None)

    result = client.fetch_messages()
    assert result == []
    assert attempts["count"] == 3


def test_oauth_login_requires_access_token() -> None:
    settings = ImapRuntimeConfig(
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_user="user@gmail.com",
        imap_password="",
        auth_mode="oauth_gmail",
        gmail_access_token=None,
        imap_mailbox="INBOX",
        imap_unseen_only=True,
        imap_fetch_limit=20,
        imap_retry_count=1,
        imap_retry_backoff_seconds=0.1,
    )
    client = IMAPMailClient(settings)

    class DummyMail:
        def authenticate(self, *_args, **_kwargs):
            return None

        def login(self, *_args, **_kwargs):
            raise AssertionError("password login should not be called for oauth mode")

    try:
        client._login(DummyMail())  # noqa: SLF001 - intentional unit test for internal login behavior
        raised = False
    except ValueError:
        raised = True

    assert raised is True
