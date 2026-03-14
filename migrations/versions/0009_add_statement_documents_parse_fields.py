"""Add parse_status and parsed_json to statement_documents

Revision ID: 0009_add_statement_documents_parse_fields
Revises: 0008_remove_user_model
Create Date: 2026-03-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0009_add_statement_documents_parse_fields"
down_revision = "0008_remove_user_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("statement_documents") as batch:
        batch.add_column(sa.Column("parse_status", sa.String(length=24), nullable=False, server_default="pending"))
        batch.add_column(sa.Column("parsed_json", sa.Text(), nullable=True))
        batch.create_check_constraint(
            op.f("ck_statement_documents_statement_documents_parse_status_enum"),
            "parse_status IN ('pending', 'parsed', 'parse_failed', 'unsupported')",
        )


def downgrade() -> None:
    with op.batch_alter_table("statement_documents") as batch:
        batch.drop_constraint(op.f("ck_statement_documents_statement_documents_parse_status_enum"), type_="check")
        batch.drop_column("parsed_json")
        batch.drop_column("parse_status")
