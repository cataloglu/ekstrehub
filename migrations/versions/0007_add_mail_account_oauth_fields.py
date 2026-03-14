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
    with op.batch_alter_table("mail_accounts") as batch:
        batch.add_column(sa.Column("auth_mode", sa.String(length=24), nullable=False, server_default="password"))
        batch.add_column(sa.Column("oauth_refresh_token", sa.String(length=1024), nullable=True))
        batch.create_check_constraint(
            op.f("ck_mail_accounts_mail_accounts_auth_mode_enum"),
            "auth_mode IN ('password', 'oauth_gmail')",
        )
        batch.alter_column("auth_mode", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("mail_accounts") as batch:
        batch.drop_constraint(op.f("ck_mail_accounts_mail_accounts_auth_mode_enum"), type_="check")
        batch.drop_column("oauth_refresh_token")
        batch.drop_column("auth_mode")
