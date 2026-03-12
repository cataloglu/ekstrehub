"""Add mail ingestion tables

Revision ID: 0003_add_mail_ingestion_tables
Revises: 0002_add_audit_logs
Create Date: 2026-02-21 02:10:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_add_mail_ingestion_tables"
down_revision = "0002_add_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emails_ingested",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=512), nullable=False),
        sa.Column("sender", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("raw_storage_key", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('processed', 'failed', 'ignored', 'duplicate')",
            name=op.f("ck_emails_ingested_emails_ingested_status_enum"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_emails_ingested")),
        sa.UniqueConstraint("message_id", name=op.f("uq_emails_ingested_message_id")),
    )
    op.create_index(op.f("ix_emails_ingested_received_at"), "emails_ingested", ["received_at"], unique=False)

    op.create_table(
        "statement_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email_ingested_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("doc_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("doc_type", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "doc_type IN ('pdf', 'csv', 'image', 'other')",
            name=op.f("ck_statement_documents_statement_documents_doc_type_enum"),
        ),
        sa.ForeignKeyConstraint(
            ["email_ingested_id"],
            ["emails_ingested.id"],
            name=op.f("fk_statement_documents_email_ingested_id_emails_ingested"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_statement_documents")),
        sa.UniqueConstraint("doc_hash", name=op.f("uq_statement_documents_doc_hash")),
    )
    op.create_index(op.f("ix_statement_documents_doc_type"), "statement_documents", ["doc_type"], unique=False)
    op.create_index(op.f("ix_statement_documents_email"), "statement_documents", ["email_ingested_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_statement_documents_email"), table_name="statement_documents")
    op.drop_index(op.f("ix_statement_documents_doc_type"), table_name="statement_documents")
    op.drop_table("statement_documents")
    op.drop_index(op.f("ix_emails_ingested_received_at"), table_name="emails_ingested")
    op.drop_table("emails_ingested")
