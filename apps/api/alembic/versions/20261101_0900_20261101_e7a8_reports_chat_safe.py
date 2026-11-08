"""reports workspace — report documents, E2E chat rooms, users.phone

Revision ID: 20261101_e7a8
Revises: 20261031_d4f6
Create Date: 2026-11-01

Three related additions for the «Отчёты» workspace and the Safe unlock:

* ``reports`` — report documents written in the editor (distinct from
  teaching materials; ownership-scoped like everything else);
* ``report_rooms`` / ``report_room_members`` / ``report_messages`` — the
  end-to-end encrypted chat. The server stores only SHA-256 of the invite
  token (join validation) and opaque base64 ciphertext (size-capped by a
  CHECK); plaintext and AES keys never reach it;
* ``users.phone`` — digits-only number bound on first Safe unlock; re-typing
  it correctly mints a short-lived Safe token (no SMS channel exists).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261101_e7a8"
down_revision = "20261031_d4f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("phone", sa.String(length=15), nullable=True),
    )

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_reports_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0", name=op.f("reports_title_not_blank")
        ),
    )
    op.create_index(
        "ix_reports_owner_updated",
        "reports",
        ["owner_id", sa.text("updated_at DESC")],
    )

    op.create_table(
        "report_rooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("invite_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_rooms")),
        sa.UniqueConstraint("invite_hash", name=op.f("uq_report_rooms_invite_hash")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_report_rooms_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "length(btrim(name)) > 0", name=op.f("report_rooms_name_not_blank")
        ),
    )

    op.create_table(
        "report_room_members",
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "room_id", "user_id", name=op.f("pk_report_room_members")
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["report_rooms.id"],
            name=op.f("fk_report_room_members_room_id_report_rooms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_room_members_user_id_users"),
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "report_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_messages")),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["report_rooms.id"],
            name=op.f("fk_report_messages_room_id_report_rooms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            name=op.f("fk_report_messages_sender_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "length(ciphertext) > 0 AND length(ciphertext) <= 300000",
            name=op.f("report_messages_ciphertext_sized"),
        ),
    )
    # id is UUIDv7 (time-ordered), so (room_id, id) doubles as a cursor index.
    op.create_index(
        "ix_report_messages_room_id", "report_messages", ["room_id", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_report_messages_room_id", table_name="report_messages")
    op.drop_table("report_messages")
    op.drop_table("report_room_members")
    op.drop_table("report_rooms")
    op.drop_index("ix_reports_owner_updated", table_name="reports")
    op.drop_table("reports")
    op.drop_column("users", "phone")
