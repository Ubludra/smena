"""Safe passkey enrollment, one-time password change and token revocation.

Revision ID: 20261108_a1c0
Revises: 20261102_f2b9
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261108_a1c0"
down_revision = "20261102_f2b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "safe_password_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users", sa.Column("safe_auth_failures", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "users", sa.Column("safe_auth_blocked_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "safe_passkeys",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_id", sa.String(length=1024), nullable=True),
        sa.Column("public_key", sa.Text(), nullable=True),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("challenge", sa.String(length=128), nullable=True),
        sa.Column("challenge_kind", sa.String(length=16), nullable=True),
        sa.Column("challenge_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_change_id", sa.String(length=64), nullable=True),
        sa.Column("pending_change_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_request_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("credential_id"),
    )


def downgrade() -> None:
    op.drop_table("safe_passkeys")
    op.drop_column("users", "safe_auth_blocked_until")
    op.drop_column("users", "safe_auth_failures")
    op.drop_column("users", "safe_password_version")
