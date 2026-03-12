"""Initial foundation schema

Revision ID: 0001_initial_foundation
Revises:
Create Date: 2026-02-21 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_initial_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "parser_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=False),
        sa.Column("parser_key", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_by", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'candidate', 'deprecated')",
            name=op.f("ck_parser_versions_parser_versions_status_enum"),
        ),
        sa.CheckConstraint(
            "created_by IN ('system', 'user')",
            name=op.f("ck_parser_versions_parser_versions_created_by_enum"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parser_versions")),
    )

    op.create_index(
        op.f("ix_parser_versions_bank_name"),
        "parser_versions",
        ["bank_name"],
        unique=False,
    )

    op.create_table(
        "cards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=False),
        sa.Column("card_alias", sa.String(length=120), nullable=False),
        sa.Column("card_last4", sa.String(length=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("card_last4 ~ '^[0-9]{4}$'", name=op.f("ck_cards_card_last4_digits")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_cards_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cards")),
    )

    op.create_index(op.f("ix_cards_user_id"), "cards", ["user_id"], unique=False)

    op.create_table(
        "statements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("parser_version_id", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_debt", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("minimum_payment", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("parse_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("total_debt >= 0", name=op.f("ck_statements_statements_total_debt_non_negative")),
        sa.CheckConstraint(
            "minimum_payment IS NULL OR minimum_payment >= 0",
            name=op.f("ck_statements_statements_minimum_payment_non_negative"),
        ),
        sa.CheckConstraint(
            "parse_confidence IS NULL OR (parse_confidence >= 0 AND parse_confidence <= 1)",
            name=op.f("ck_statements_statements_confidence_range"),
        ),
        sa.CheckConstraint(
            "status IN ('accepted', 'review_needed')",
            name=op.f("ck_statements_statements_status_enum"),
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["cards.id"],
            name=op.f("fk_statements_card_id_cards"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parser_version_id"],
            ["parser_versions.id"],
            name=op.f("fk_statements_parser_version_id_parser_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_statements_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_statements")),
    )

    op.create_index(op.f("ix_statements_user_id"), "statements", ["user_id"], unique=False)
    op.create_index(op.f("ix_statements_card_id"), "statements", ["card_id"], unique=False)
    op.create_index(op.f("ix_statements_due_date"), "statements", ["due_date"], unique=False)

    op.create_table(
        "parser_change_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=False),
        sa.Column("current_parser_version_id", sa.Integer(), nullable=True),
        sa.Column("candidate_parser_version_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("validation_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("approval_status", sa.String(length=24), nullable=False),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "reason IN ('drift_detected', 'manual')",
            name=op.f("ck_parser_change_requests_parser_change_requests_reason_enum"),
        ),
        sa.CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected')",
            name=op.f("ck_parser_change_requests_parser_change_requests_approval_status_enum"),
        ),
        sa.CheckConstraint(
            "validation_score IS NULL OR (validation_score >= 0 AND validation_score <= 1)",
            name=op.f("ck_parser_change_requests_parser_change_requests_validation_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_parser_version_id"],
            ["parser_versions.id"],
            name=op.f("fk_parser_change_requests_candidate_parser_version_id_parser_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["current_parser_version_id"],
            ["parser_versions.id"],
            name=op.f("fk_parser_change_requests_current_parser_version_id_parser_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parser_change_requests")),
    )

    op.create_index(
        op.f("ix_parser_change_requests_approval_status"),
        "parser_change_requests",
        ["approval_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parser_change_requests_bank_name"),
        "parser_change_requests",
        ["bank_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_parser_change_requests_bank_name"), table_name="parser_change_requests")
    op.drop_index(op.f("ix_parser_change_requests_approval_status"), table_name="parser_change_requests")
    op.drop_table("parser_change_requests")

    op.drop_index(op.f("ix_statements_due_date"), table_name="statements")
    op.drop_index(op.f("ix_statements_card_id"), table_name="statements")
    op.drop_index(op.f("ix_statements_user_id"), table_name="statements")
    op.drop_table("statements")

    op.drop_index(op.f("ix_cards_user_id"), table_name="cards")
    op.drop_table("cards")

    op.drop_index(op.f("ix_parser_versions_bank_name"), table_name="parser_versions")
    op.drop_table("parser_versions")

    op.drop_table("users")
