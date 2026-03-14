"""Add mail accounts and ingestion foreign keys

Revision ID: 0006_add_mail_accounts_and_fks
Revises: 0005_add_ingestion_idempotency_key
Create Date: 2026-02-21 03:40:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_add_mail_accounts_and_fks"
down_revision = "0005_add_ingestion_idempotency_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mail_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("account_label", sa.String(length=120), nullable=False),
        sa.Column("imap_host", sa.String(length=255), nullable=False),
        sa.Column("imap_port", sa.Integer(), nullable=False),
        sa.Column("imap_user", sa.String(length=255), nullable=False),
        sa.Column("imap_password", sa.String(length=255), nullable=False),
        sa.Column("mailbox", sa.String(length=120), nullable=False),
        sa.Column("unseen_only", sa.Boolean(), nullable=False),
        sa.Column("fetch_limit", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("retry_backoff_seconds", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "provider IN ('gmail', 'outlook', 'custom')",
            name=op.f("ck_mail_accounts_mail_accounts_provider_enum"),
        ),
        sa.CheckConstraint("imap_port > 0", name=op.f("ck_mail_accounts_mail_accounts_imap_port_positive")),
        sa.CheckConstraint("fetch_limit > 0", name=op.f("ck_mail_accounts_mail_accounts_fetch_limit_positive")),
        sa.CheckConstraint("retry_count > 0", name=op.f("ck_mail_accounts_mail_accounts_retry_count_positive")),
        sa.CheckConstraint(
            "retry_backoff_seconds > 0",
            name=op.f("ck_mail_accounts_mail_accounts_retry_backoff_positive"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_accounts")),
    )

    with op.batch_alter_table("emails_ingested") as batch:
        batch.add_column(sa.Column("mail_account_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_emails_ingested_mail_account_id_mail_accounts"),
            "mail_accounts",
            ["mail_account_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(op.f("ix_emails_ingested_mail_account_id"), ["mail_account_id"], unique=False)

    with op.batch_alter_table("mail_ingestion_runs") as batch:
        batch.add_column(sa.Column("mail_account_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_mail_ingestion_runs_mail_account_id_mail_accounts"),
            "mail_accounts",
            ["mail_account_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(op.f("ix_mail_ingestion_runs_mail_account_id"), ["mail_account_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("mail_ingestion_runs") as batch:
        batch.drop_index(op.f("ix_mail_ingestion_runs_mail_account_id"))
        batch.drop_constraint(op.f("fk_mail_ingestion_runs_mail_account_id_mail_accounts"), type_="foreignkey")
        batch.drop_column("mail_account_id")

    with op.batch_alter_table("emails_ingested") as batch:
        batch.drop_index(op.f("ix_emails_ingested_mail_account_id"))
        batch.drop_constraint(op.f("fk_emails_ingested_mail_account_id_mail_accounts"), type_="foreignkey")
        batch.drop_column("mail_account_id")

    op.drop_table("mail_accounts")
