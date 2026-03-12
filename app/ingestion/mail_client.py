from __future__ import annotations

import email
from dataclasses import dataclass
from datetime import datetime
from email.message import Message
from email.utils import parsedate_to_datetime
import imaplib
from time import sleep

from app.ingestion.runtime_config import ImapRuntimeConfig


@dataclass
class AttachmentPayload:
    file_name: str
    content_type: str
    content: bytes


@dataclass
class MailMessagePayload:
    message_id: str
    sender: str | None
    subject: str | None
    received_at: datetime | None
    attachments: list[AttachmentPayload]


class IMAPMailClient:
    def __init__(self, settings: ImapRuntimeConfig) -> None:
        self._settings = settings

    def fetch_messages(self) -> list[MailMessagePayload]:
        last_error: Exception | None = None
        for attempt in range(1, self._settings.imap_retry_count + 1):
            try:
                return self._fetch_messages_once()
            except (imaplib.IMAP4.error, OSError) as exc:
                last_error = exc
                if attempt < self._settings.imap_retry_count:
                    sleep(self._settings.imap_retry_backoff_seconds * attempt)
        if last_error:
            raise last_error
        return []

    @staticmethod
    def _quote_mailbox(name: str) -> str:
        """Return IMAP-safe mailbox name. Names with spaces or special chars need quoting."""
        if " " in name or name.startswith("["):
            # Escape any existing double-quotes inside the name, then wrap
            escaped = name.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return name

    def _fetch_messages_once(self) -> list[MailMessagePayload]:
        query = "UNSEEN" if self._settings.imap_unseen_only else "ALL"
        with imaplib.IMAP4_SSL(self._settings.imap_host, self._settings.imap_port) as mail:
            self._login(mail)
            mailbox = self._quote_mailbox(self._settings.imap_mailbox)
            sel_status, sel_data = mail.select(mailbox)
            if sel_status != "OK":
                raise imaplib.IMAP4.error(
                    f"SELECT command failed for mailbox {self._settings.imap_mailbox!r}: {sel_data}"
                )
            status, search_data = mail.search(None, query)
            if status != "OK":
                return []

            ids = search_data[0].split()[-self._settings.imap_fetch_limit :]
            messages: list[MailMessagePayload] = []
            for message_id in ids:
                fetch_status, fetch_data = mail.fetch(message_id, "(RFC822)")
                if fetch_status != "OK" or not fetch_data:
                    continue
                raw_email = fetch_data[0][1]
                parsed = email.message_from_bytes(raw_email)
                payload = self._parse_message(parsed)
                if payload:
                    messages.append(payload)
            return messages

    def _login(self, mail: imaplib.IMAP4_SSL) -> None:
        if self._settings.auth_mode == "oauth_gmail":
            access_token = self._settings.gmail_access_token
            if not access_token:
                raise ValueError("Gmail OAuth access token is required for oauth_gmail auth mode.")
            auth_string = f"user={self._settings.imap_user}\x01auth=Bearer {access_token}\x01\x01"
            mail.authenticate("XOAUTH2", lambda _: auth_string.encode("utf-8"))
            return
        mail.login(self._settings.imap_user, self._settings.imap_password)

    def _parse_message(self, message: Message) -> MailMessagePayload | None:
        raw_message_id = (message.get("Message-ID") or "").strip()
        if not raw_message_id:
            return None

        date_header = (message.get("Date") or "").strip()
        received_at: datetime | None = None
        if date_header:
            try:
                received_at = parsedate_to_datetime(date_header)
            except (TypeError, ValueError):
                received_at = None

        attachments: list[AttachmentPayload] = []
        for part in message.walk():
            content_disposition = (part.get("Content-Disposition") or "").lower()
            content_type = (part.get_content_type() or "").lower()

            # Accept both explicit attachments and inline parts that have a filename
            # (e.g. DenizBank sends PDFs as inline with filename=Ekstre.pdf)
            is_attachment = "attachment" in content_disposition
            is_named_inline = "inline" in content_disposition or not content_disposition
            file_name = part.get_filename() or ""

            if not is_attachment and not (is_named_inline and file_name):
                continue
            if not file_name:
                continue

            # Only pick up document types we can handle; skip HTML/text parts
            doc_ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
            is_doc = doc_ext in ("pdf", "csv", "png", "jpg", "jpeg", "webp") or (
                content_type.startswith(("application/pdf", "text/csv", "image/"))
            )
            if not is_doc:
                continue

            content = part.get_payload(decode=True) or b""
            if not content:
                continue
            attachments.append(
                AttachmentPayload(
                    file_name=file_name,
                    content_type=part.get_content_type() or "application/octet-stream",
                    content=content,
                )
            )

        return MailMessagePayload(
            message_id=raw_message_id,
            sender=message.get("From"),
            subject=message.get("Subject"),
            received_at=received_at,
            attachments=attachments,
        )
