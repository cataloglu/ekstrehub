"""Add OAuth fields to mail accounts

Revision ID: 0007_add_mail_account_oauth_fields
Revises: 0006_add_mail_accounts_and_fks
Create Date: 2026-02-21 04:05:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_add_mail_account_oauth_fields"
down_revision = "0006_add_mail_accounts_and_fks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mail_accounts", sa.Column("auth_mode", sa.String(length=24), nullable=False, server_default="password"))
    op.add_column("mail_accounts", sa.Column("oauth_refresh_token", sa.String(length=1024), nullable=True))
    op.create_check_constraint(
        op.f("ck_mail_accounts_mail_accounts_auth_mode_enum"),
        "mail_accounts",
        "auth_mode IN ('password', 'oauth_gmail')",
    )
    op.alter_column("mail_accounts", "auth_mode", server_default=None)


def downgrade() -> None:
    op.drop_constraint(op.f("ck_mail_accounts_mail_accounts_auth_mode_enum"), "mail_accounts", type_="check")
    op.drop_column("mail_accounts", "oauth_refresh_token")
    op.drop_column("mail_accounts", "auth_mode")
