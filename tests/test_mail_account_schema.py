import pytest

from app.schemas.mail_accounts import MailAccountCreateRequest


def test_mail_account_schema_requires_refresh_token_for_gmail_oauth() -> None:
    with pytest.raises(ValueError):
        MailAccountCreateRequest(
            provider="gmail",
            auth_mode="oauth_gmail",
            account_label="Gmail OAuth",
            imap_host="imap.gmail.com",
            imap_port=993,
            imap_user="user@gmail.com",
            imap_password="",
            oauth_refresh_token=None,
            mailbox="INBOX",
            unseen_only=True,
            fetch_limit=20,
            retry_count=3,
            retry_backoff_seconds=1.5,
            is_active=True,
        )


def test_mail_account_schema_requires_password_for_password_mode() -> None:
    with pytest.raises(ValueError):
        MailAccountCreateRequest(
            provider="custom",
            auth_mode="password",
            account_label="Custom",
            imap_host="imap.example.com",
            imap_port=993,
            imap_user="user@example.com",
            imap_password="",
            oauth_refresh_token=None,
            mailbox="INBOX",
            unseen_only=True,
            fetch_limit=20,
            retry_count=3,
            retry_backoff_seconds=1.5,
            is_active=True,
        )
