from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select

from app.config import get_settings
import app.app_settings as app_settings_module
from app.db.models import EmailIngested, MailAccount, MailIngestionRun, StatementDocument
from app.db.session import get_session_factory
from app.ingestion.bank_profiles import BANK_PROFILES
from app.ingestion.csv_parser import parse_statement_csv
from app.ingestion.gmail_oauth import GmailOAuthError, refresh_access_token
from app.ingestion.mail_client import IMAPMailClient
from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.runtime_config import ImapRuntimeConfig, runtime_from_env, runtime_from_mail_account
from app.ingestion.learned_rules import load_learned_rule_dict, maybe_train_learned_rules
from app.ingestion.statement_parser import _detect_bank_from_text, is_llm_failure_empty, parse_statement

log = logging.getLogger(__name__)


@dataclass
class IngestionSummary:
    run_id: int = 0
    scanned_messages: int = 0
    processed_messages: int = 0
    duplicate_messages: int = 0
    saved_documents: int = 0
    duplicate_documents: int = 0
    skipped_attachments: int = 0
    failed_messages: int = 0
    csv_rows_parsed: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "run_id": self.run_id,
            "scanned_messages": self.scanned_messages,
            "processed_messages": self.processed_messages,
            "duplicate_messages": self.duplicate_messages,
            "saved_documents": self.saved_documents,
            "duplicate_documents": self.duplicate_documents,
            "skipped_attachments": self.skipped_attachments,
            "failed_messages": self.failed_messages,
            "csv_rows_parsed": self.csv_rows_parsed,
        }


class MailIngestionService:
    def __init__(self, mail_account: MailAccount | None = None) -> None:
        self._settings = get_settings()
        self._mail_account = mail_account
        runtime = runtime_from_mail_account(mail_account) if mail_account else runtime_from_env(self._settings)
        self._client = IMAPMailClient(self._prepare_runtime(runtime))

    def _prepare_runtime(self, runtime: ImapRuntimeConfig) -> ImapRuntimeConfig:
        if runtime.auth_mode != "oauth_gmail":
            return runtime
        if not self._mail_account or not self._mail_account.oauth_refresh_token:
            raise GmailOAuthError("Missing oauth_refresh_token for Gmail OAuth account.")
        access_token = refresh_access_token(self._settings, self._mail_account.oauth_refresh_token)
        return ImapRuntimeConfig(
            imap_host=runtime.imap_host,
            imap_port=runtime.imap_port,
            imap_user=runtime.imap_user,
            imap_password=runtime.imap_password,
            auth_mode=runtime.auth_mode,
            gmail_access_token=access_token,
            imap_mailbox=runtime.imap_mailbox,
            imap_unseen_only=runtime.imap_unseen_only,
            imap_fetch_limit=runtime.imap_fetch_limit,
            imap_retry_count=runtime.imap_retry_count,
            imap_retry_backoff_seconds=runtime.imap_retry_backoff_seconds,
        )

    def run_sync(self, idempotency_key: str | None = None) -> tuple[dict[str, int], bool]:
        summary = IngestionSummary()

        session_factory = get_session_factory()
        with session_factory() as session:
            if idempotency_key:
                existing_run = session.scalar(
                    select(MailIngestionRun).where(MailIngestionRun.idempotency_key == idempotency_key)
                )
                if existing_run:
                    return (
                        {
                            "run_id": existing_run.id,
                            "scanned_messages": existing_run.scanned_messages,
                            "processed_messages": existing_run.processed_messages,
                            "duplicate_messages": existing_run.duplicate_messages,
                            "saved_documents": existing_run.saved_documents,
                            "duplicate_documents": existing_run.duplicate_documents,
                            "skipped_attachments": existing_run.skipped_attachments,
                            "failed_messages": existing_run.failed_messages,
                            "csv_rows_parsed": existing_run.csv_rows_parsed,
                        },
                        True,
                    )

            messages = self._client.fetch_messages()
            summary.scanned_messages = len(messages)

            run = MailIngestionRun(
                status="running",
                idempotency_key=idempotency_key,
                mail_account_id=self._mail_account.id if self._mail_account else None,
            )
            session.add(run)
            session.flush()
            summary.run_id = run.id
            session.commit()

            for message in messages:
                try:
                    existing_message = session.scalar(
                        select(EmailIngested).where(EmailIngested.message_id == message.message_id)
                    )
                    if existing_message:
                        summary.duplicate_messages += 1
                        continue

                    email_row = EmailIngested(
                        mail_account_id=self._mail_account.id if self._mail_account else None,
                        message_id=message.message_id,
                        sender=message.sender,
                        bank_name=self._detect_bank_name(message.sender, message.subject),
                        subject=message.subject,
                        received_at=message.received_at,
                        status="processed",
                    )
                    session.add(email_row)
                    session.flush()

                    supported_docs = 0
                    for attachment in message.attachments:
                        doc_type = self._resolve_doc_type(attachment.file_name, attachment.content_type)
                        if doc_type == "other":
                            summary.skipped_attachments += 1
                            continue

                        doc_hash = sha256(attachment.content).hexdigest()
                        existing_doc = session.scalar(
                            select(StatementDocument).where(StatementDocument.doc_hash == doc_hash)
                        )
                        if existing_doc:
                            summary.duplicate_documents += 1
                            continue

                        parse_status = "pending"
                        parsed_json: str | None = None

                        if doc_type == "csv":
                            try:
                                parsed_rows = parse_statement_csv(attachment.content)
                                parse_status = "parsed"
                                parsed_json = json.dumps(
                                    {"rows": [r.__dict__ if hasattr(r, "__dict__") else r for r in parsed_rows]},
                                    default=str,
                                )
                            except Exception:
                                parse_status = "parse_failed"
                                summary.skipped_attachments += 1
                                continue
                            summary.csv_rows_parsed += len(parsed_rows)

                        elif doc_type == "pdf":
                            try:
                                text = extract_text_from_pdf(attachment.content)
                                bank = self._detect_bank_name(message.sender, message.subject) or _detect_bank_from_text(
                                    text
                                )
                                _learned = load_learned_rule_dict(session, bank)
                                # Always read LLM config at parse-time so UI changes take effect immediately
                                _llm = app_settings_module.get_llm_config()
                                _llm_url = _llm["llm_api_url"] if _llm.get("llm_enabled") else ""
                                result = parse_statement(
                                    text,
                                    bank,
                                    llm_api_url=_llm_url,
                                    llm_model=_llm["llm_model"],
                                    llm_api_key=_llm["llm_api_key"],
                                    llm_timeout_seconds=_llm["llm_timeout_seconds"],
                                    llm_min_tx_threshold=_llm.get("llm_min_tx_threshold", 0),
                                    learned_rules=_learned,
                                )
                                if (
                                    result
                                    and "llm_parsed" in (result.parse_notes or [])
                                    and len(result.transactions) > 0
                                ):
                                    maybe_train_learned_rules(
                                        session,
                                        result.bank_name or bank,
                                        text,
                                        result,
                                        _llm,
                                    )

                                # ── Katman 3: İçerik bazlı duplicate kontrolü ──
                                # Banka + dönem + toplam tutar aynıysa başka bir
                                # email/PDF'den zaten gelmiş demektir; tekrar ekleme.
                                if (
                                    result.bank_name
                                    and result.statement_period_start
                                    and result.statement_period_end
                                    and result.total_due_try is not None
                                ):
                                    content_dupe = session.scalar(
                                        select(StatementDocument).where(
                                            StatementDocument.parse_status == "parsed",
                                            StatementDocument.parsed_json.contains(
                                                f'"period_start": "{result.statement_period_start}"'
                                            ),
                                            StatementDocument.parsed_json.contains(
                                                f'"period_end": "{result.statement_period_end}"'
                                            ),
                                            StatementDocument.parsed_json.contains(
                                                f'"bank_name": "{result.bank_name}"'
                                            ),
                                        )
                                    )
                                    if content_dupe:
                                        log.info(
                                            "content_duplicate_skipped bank=%s period=%s/%s existing_doc=%d",
                                            result.bank_name,
                                            result.statement_period_start,
                                            result.statement_period_end,
                                            content_dupe.id,
                                        )
                                        summary.duplicate_documents += 1
                                        continue

                                parse_status = "parse_failed" if is_llm_failure_empty(result) else "parsed"
                                parsed_json = json.dumps(
                                    {
                                        "bank_name": result.bank_name,
                                        "card_number": result.card_number,
                                        "period_start": str(result.statement_period_start) if result.statement_period_start else None,
                                        "period_end": str(result.statement_period_end) if result.statement_period_end else None,
                                        "due_date": str(result.due_date) if result.due_date else None,
                                        "total_due_try": result.total_due_try,
                                        "minimum_due_try": result.minimum_due_try,
                                        "transactions": [
                                            {
                                                "date": str(tx.date) if tx.date else None,
                                                "description": tx.description,
                                                "amount": tx.amount,
                                                "currency": tx.currency,
                                            }
                                            for tx in result.transactions
                                        ],
                                        "parse_notes": result.parse_notes,
                                    },
                                    ensure_ascii=False,
                                )
                                log.info(
                                    "pdf_parsed bank=%s transactions=%d total=%s",
                                    result.bank_name,
                                    len(result.transactions),
                                    result.total_due_try,
                                )
                            except Exception as exc:
                                parse_status = "parse_failed"
                                log.warning("pdf_parse_failed file=%s err=%s", attachment.file_name, exc)

                        session.add(
                            StatementDocument(
                                email_ingested_id=email_row.id,
                                file_name=attachment.file_name,
                                mime_type=attachment.content_type,
                                storage_key=None,
                                doc_hash=doc_hash,
                                file_size_bytes=len(attachment.content),
                                doc_type=doc_type,
                                parse_status=parse_status,
                                parsed_json=parsed_json,
                            )
                        )
                        summary.saved_documents += 1
                        supported_docs += 1

                    if supported_docs == 0:
                        email_row.status = "ignored"

                    summary.processed_messages += 1
                    session.commit()
                except Exception:
                    summary.failed_messages += 1
                    session.rollback()

            run = session.get(MailIngestionRun, summary.run_id)
            if run:
                run.scanned_messages = summary.scanned_messages
                run.processed_messages = summary.processed_messages
                run.duplicate_messages = summary.duplicate_messages
                run.saved_documents = summary.saved_documents
                run.duplicate_documents = summary.duplicate_documents
                run.skipped_attachments = summary.skipped_attachments
                run.failed_messages = summary.failed_messages
                run.csv_rows_parsed = summary.csv_rows_parsed
                run.finished_at = datetime.now(UTC)
                run.status = "completed_with_errors" if summary.failed_messages else "completed"
                session.commit()

        return summary.to_dict(), False

    @staticmethod
    def _resolve_doc_type(file_name: str, content_type: str) -> str:
        lower_name = file_name.lower()
        lower_type = (content_type or "").lower()
        if lower_name.endswith(".pdf") or "pdf" in lower_type:
            return "pdf"
        if lower_name.endswith(".csv") or "csv" in lower_type:
            return "csv"
        if lower_name.endswith((".png", ".jpg", ".jpeg", ".webp")) or lower_type.startswith("image/"):
            return "image"
        return "other"

    @staticmethod
    def _detect_bank_name(sender: str | None, subject: str | None) -> str | None:
        text = f"{sender or ''} {subject or ''}".lower()
        for profile in BANK_PROFILES:
            for marker in profile.markers:
                if marker in text:
                    return profile.bank_name
        return None
