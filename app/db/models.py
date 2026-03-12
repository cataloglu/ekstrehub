from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    card_alias: Mapped[str] = mapped_column(String(120), nullable=False)
    card_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ParserVersion(Base):
    __tablename__ = "parser_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    parser_key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="candidate")
    created_by: Mapped[str] = mapped_column(String(24), nullable=False, default="system")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'candidate', 'deprecated')",
            name="parser_versions_status_enum",
        ),
        CheckConstraint(
            "created_by IN ('system', 'user')",
            name="parser_versions_created_by_enum",
        ),
    )


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    parser_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("parser_versions.id", ondelete="SET NULL"), nullable=True
    )
    period_start: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_debt: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    minimum_payment: Mapped[Numeric | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    parse_confidence: Mapped[Numeric | None] = mapped_column(Numeric(5, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="accepted")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("total_debt >= 0", name="statements_total_debt_non_negative"),
        CheckConstraint(
            "minimum_payment IS NULL OR minimum_payment >= 0",
            name="statements_minimum_payment_non_negative",
        ),
        CheckConstraint(
            "parse_confidence IS NULL OR (parse_confidence >= 0 AND parse_confidence <= 1)",
            name="statements_confidence_range",
        ),
        CheckConstraint(
            "status IN ('accepted', 'review_needed')",
            name="statements_status_enum",
        ),
    )


class ParserChangeRequest(Base):
    __tablename__ = "parser_change_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    current_parser_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("parser_versions.id", ondelete="SET NULL"), nullable=True
    )
    candidate_parser_version_id: Mapped[int] = mapped_column(
        ForeignKey("parser_versions.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_score: Mapped[Numeric | None] = mapped_column(Numeric(5, 4), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "reason IN ('drift_detected', 'manual')",
            name="parser_change_requests_reason_enum",
        ),
        CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected')",
            name="parser_change_requests_approval_status_enum",
        ),
        CheckConstraint(
            "validation_score IS NULL OR (validation_score >= 0 AND validation_score <= 1)",
            name="parser_change_requests_validation_score_range",
        ),
    )


class EmailIngested(Base):
    __tablename__ = "emails_ingested"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mail_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    message_id: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    received_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="processed")
    raw_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('processed', 'failed', 'ignored', 'duplicate')",
            name="emails_ingested_status_enum",
        ),
    )


class StatementDocument(Base):
    __tablename__ = "statement_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email_ingested_id: Mapped[int] = mapped_column(
        ForeignKey("emails_ingested.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    doc_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(24), nullable=False)
    # parser output
    parse_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    parsed_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "doc_type IN ('pdf', 'csv', 'image', 'other')",
            name="statement_documents_doc_type_enum",
        ),
        CheckConstraint(
            "parse_status IN ('pending', 'parsed', 'parse_failed', 'unsupported')",
            name="statement_documents_parse_status_enum",
        ),
    )


class MailIngestionRun(Base):
    __tablename__ = "mail_ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mail_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="running")
    scanned_messages: Mapped[int] = mapped_column(nullable=False, default=0)
    processed_messages: Mapped[int] = mapped_column(nullable=False, default=0)
    duplicate_messages: Mapped[int] = mapped_column(nullable=False, default=0)
    saved_documents: Mapped[int] = mapped_column(nullable=False, default=0)
    duplicate_documents: Mapped[int] = mapped_column(nullable=False, default=0)
    skipped_attachments: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_messages: Mapped[int] = mapped_column(nullable=False, default=0)
    csv_rows_parsed: Mapped[int] = mapped_column(nullable=False, default=0)
    started_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'completed_with_errors', 'failed')",
            name="mail_ingestion_runs_status_enum",
        ),
    )


class MailAccount(Base):
    __tablename__ = "mail_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(24), nullable=False, default="custom")
    auth_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="password")
    account_label: Mapped[str] = mapped_column(String(120), nullable=False)
    imap_host: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_port: Mapped[int] = mapped_column(nullable=False, default=993)
    imap_user: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_password: Mapped[str] = mapped_column(String(255), nullable=False)
    oauth_refresh_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mailbox: Mapped[str] = mapped_column(String(120), nullable=False, default="INBOX")
    unseen_only: Mapped[bool] = mapped_column(nullable=False, default=True)
    fetch_limit: Mapped[int] = mapped_column(nullable=False, default=20)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=3)
    retry_backoff_seconds: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False, default=1.5)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "provider IN ('gmail', 'outlook', 'custom')",
            name="mail_accounts_provider_enum",
        ),
        CheckConstraint(
            "auth_mode IN ('password', 'oauth_gmail')",
            name="mail_accounts_auth_mode_enum",
        ),
        CheckConstraint("imap_port > 0", name="mail_accounts_imap_port_positive"),
        CheckConstraint("fetch_limit > 0", name="mail_accounts_fetch_limit_positive"),
        CheckConstraint("retry_count > 0", name="mail_accounts_retry_count_positive"),
        CheckConstraint(
            "retry_backoff_seconds > 0",
            name="mail_accounts_retry_backoff_positive",
        ),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('system', 'user')",
            name="audit_logs_actor_type_enum",
        ),
    )
