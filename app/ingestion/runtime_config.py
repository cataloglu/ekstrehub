from dataclasses import dataclass
from decimal import Decimal

from app.config import AppConfig
from app.db.models import MailAccount


@dataclass(frozen=True)
class ImapRuntimeConfig:
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    auth_mode: str
    gmail_access_token: str | None
    imap_mailbox: str
    imap_unseen_only: bool
    imap_fetch_limit: int
    imap_retry_count: int
    imap_retry_backoff_seconds: float


def runtime_from_env(settings: AppConfig) -> ImapRuntimeConfig:
    return ImapRuntimeConfig(
        imap_host=settings.imap_host,
        imap_port=settings.imap_port,
        imap_user=settings.imap_user,
        imap_password=settings.imap_password,
        auth_mode="password",
        gmail_access_token=None,
        imap_mailbox=settings.imap_mailbox,
        imap_unseen_only=settings.imap_unseen_only,
        imap_fetch_limit=settings.imap_fetch_limit,
        imap_retry_count=settings.imap_retry_count,
        imap_retry_backoff_seconds=settings.imap_retry_backoff_seconds,
    )


def runtime_from_mail_account(account: MailAccount) -> ImapRuntimeConfig:
    backoff = float(account.retry_backoff_seconds) if isinstance(account.retry_backoff_seconds, Decimal) else float(
        account.retry_backoff_seconds
    )
    return ImapRuntimeConfig(
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        imap_user=account.imap_user,
        imap_password=account.imap_password,
        auth_mode=account.auth_mode,
        gmail_access_token=None,
        imap_mailbox=account.mailbox,
        imap_unseen_only=account.unseen_only,
        imap_fetch_limit=account.fetch_limit,
        imap_retry_count=account.retry_count,
        imap_retry_backoff_seconds=backoff,
    )
