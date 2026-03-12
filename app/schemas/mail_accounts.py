from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


MailProvider = Literal["gmail", "outlook", "custom"]
MailAuthMode = Literal["password", "oauth_gmail"]


class MailAccountCreateRequest(BaseModel):
    provider: MailProvider = "custom"
    auth_mode: MailAuthMode = "password"
    account_label: str = Field(min_length=1, max_length=120)
    imap_host: str = Field(min_length=1, max_length=255)
    imap_port: int = Field(default=993, gt=0)
    imap_user: str = Field(min_length=1, max_length=255)
    imap_password: str = Field(default="", max_length=255)
    oauth_refresh_token: str | None = Field(default=None, max_length=1024)
    mailbox: str = Field(default="INBOX", min_length=1, max_length=120)
    unseen_only: bool = True
    fetch_limit: int = Field(default=20, gt=0)
    retry_count: int = Field(default=3, gt=0)
    retry_backoff_seconds: float = Field(default=1.5, gt=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_auth_mode_fields(self):
        if self.auth_mode == "oauth_gmail":
            if not self.oauth_refresh_token:
                raise ValueError("oauth_refresh_token is required for oauth_gmail mode.")
        else:
            if not self.imap_password:
                raise ValueError("imap_password is required for password mode.")
        return self


class MailAccountResponse(BaseModel):
    id: int
    provider: MailProvider
    auth_mode: MailAuthMode
    account_label: str
    imap_host: str
    imap_port: int
    imap_user: str
    mailbox: str
    unseen_only: bool
    fetch_limit: int
    retry_count: int
    retry_backoff_seconds: float
    is_active: bool
    created_at: datetime


class MailAccountListResponse(BaseModel):
    items: list[MailAccountResponse]
