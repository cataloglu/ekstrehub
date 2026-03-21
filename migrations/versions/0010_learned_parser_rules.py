"""Per-bank learned regex rules (train once from LLM, parse locally later).

Revision ID: 0010_learned_parser_rules
Revises: 0009_add_statement_documents_parse_fields
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_learned_parser_rules"
down_revision = "0009_add_statement_documents_parse_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learned_parser_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bank_name", sa.String(length=128), nullable=False),
        sa.Column("rules_json", sa.Text(), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learned_parser_rules")),
        sa.UniqueConstraint("bank_name", name=op.f("uq_learned_parser_rules_bank_name")),
    )
    op.create_index(op.f("ix_learned_parser_rules_bank_name"), "learned_parser_rules", ["bank_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_learned_parser_rules_bank_name"), table_name="learned_parser_rules")
    op.drop_table("learned_parser_rules")
