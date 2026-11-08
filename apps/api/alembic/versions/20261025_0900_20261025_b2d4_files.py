"""files — teacher-uploaded files (metadata; content on disk)

Revision ID: 20261025_b2d4
Revises: 20261024_a5c7
Create Date: 2026-10-25

The DB row stores metadata only. The stored_name column is a server-generated
"<uuid>.<ext>" value — the client never influences the storage path, so no
path-traversal surface exists. File bytes live under UPLOAD_DIR on a dedicated
compose volume; deleting the row removes the blob too (best-effort).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261025_b2d4"
down_revision = "20261024_a5c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_files")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_files_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "length(btrim(original_name)) > 0",
            name=op.f("ck_files_original_name_not_blank"),
        ),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_files_size_non_negative")),
    )
    op.create_index(
        "ix_files_owner_created",
        "files",
        ["owner_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_files_owner_created", table_name="files")
    op.drop_table("files")
