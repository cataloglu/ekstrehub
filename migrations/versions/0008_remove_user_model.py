"""Remove user model: drop user_id FKs from cards/statements, drop users table.

Revision ID: 0008_remove_user_model
Revises: 0007_add_mail_account_oauth_fields
Create Date: 2026-02-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_remove_user_model"
down_revision = "0007_add_mail_account_oauth_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- statements: drop index, FK + column user_id ---
    with op.batch_alter_table("statements") as batch:
        batch.drop_index("ix_statements_user_id")
        batch.drop_constraint("fk_statements_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")

    # --- cards: drop index, FK + column user_id, add is_active ---
    with op.batch_alter_table("cards") as batch:
        batch.drop_index("ix_cards_user_id")
        batch.drop_constraint("fk_cards_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))

    # --- drop users table ---
    op.drop_table("users")


def downgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Istanbul"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    with op.batch_alter_table("cards") as batch:
        batch.drop_column("is_active")
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=False))
        batch.create_foreign_key("fk_cards_user_id_users", "users", ["user_id"], ["id"], ondelete="CASCADE")

    with op.batch_alter_table("statements") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=False))
        batch.create_foreign_key("fk_statements_user_id_users", "users", ["user_id"], ["id"], ondelete="CASCADE")
