"""Add ingestion runs and bank name to emails

Revision ID: 0004_add_ingestion_runs_and_bank_name
Revises: 0003_add_mail_ingestion_tables
Create Date: 2026-02-21 02:40:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_add_ingestion_runs_and_bank_name"
down_revision = "0003_add_mail_ingestion_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("emails_ingested", sa.Column("bank_name", sa.String(length=64), nullable=True))

    op.create_table(
        "mail_ingestion_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("scanned_messages", sa.Integer(), nullable=False),
        sa.Column("processed_messages", sa.Integer(), nullable=False),
        sa.Column("duplicate_messages", sa.Integer(), nullable=False),
        sa.Column("saved_documents", sa.Integer(), nullable=False),
        sa.Column("duplicate_documents", sa.Integer(), nullable=False),
        sa.Column("skipped_attachments", sa.Integer(), nullable=False),
        sa.Column("failed_messages", sa.Integer(), nullable=False),
        sa.Column("csv_rows_parsed", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'completed_with_errors', 'failed')",
            name=op.f("ck_mail_ingestion_runs_mail_ingestion_runs_status_enum"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_ingestion_runs")),
    )
    op.create_index(op.f("ix_mail_ingestion_runs_started_at"), "mail_ingestion_runs", ["started_at"], unique=False)
    op.create_index(op.f("ix_mail_ingestion_runs_status"), "mail_ingestion_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mail_ingestion_runs_status"), table_name="mail_ingestion_runs")
    op.drop_index(op.f("ix_mail_ingestion_runs_started_at"), table_name="mail_ingestion_runs")
    op.drop_table("mail_ingestion_runs")
    op.drop_column("emails_ingested", "bank_name")
