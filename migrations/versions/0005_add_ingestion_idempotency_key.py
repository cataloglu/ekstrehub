"""Add idempotency key to ingestion runs

Revision ID: 0005_add_ingestion_idempotency_key
Revises: 0004_add_ingestion_runs_and_bank_name
Create Date: 2026-02-21 03:10:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_add_ingestion_idempotency_key"
down_revision = "0004_add_ingestion_runs_and_bank_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mail_ingestion_runs") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch.create_unique_constraint(op.f("uq_mail_ingestion_runs_idempotency_key"), ["idempotency_key"])


def downgrade() -> None:
    with op.batch_alter_table("mail_ingestion_runs") as batch:
        batch.drop_constraint(op.f("uq_mail_ingestion_runs_idempotency_key"), type_="unique")
        batch.drop_column("idempotency_key")
