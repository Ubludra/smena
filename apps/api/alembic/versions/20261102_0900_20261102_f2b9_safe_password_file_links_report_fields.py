"""Safe password, file links beyond materials, report requisites

Revision ID: 20261102_f2b9
Revises: 20261101_e7a8
Create Date: 2026-11-02

Three related changes requested after the first Safe/reports iteration:

* ``users.safe_password_hash`` replaces ``users.phone``: the Safe unlock
  factor becomes a dedicated password (scrypt hash — the plaintext never
  touches the database), not the account phone number;
* ``files.lesson_plan_id / assessment_id / assignment_id / report_id`` —
  the same SET NULL attachment pattern as ``material_id``, so files can be
  attached to any workspace entity, not only materials;
* ``reports.class_name`` / ``reports.period`` — report requisites
  (class, reporting period) the editor shows as structured fields.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261102_f2b9"
down_revision = "20261101_e7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Safe: password hash replaces the bound phone -----------------------
    op.add_column(
        "users",
        sa.Column("safe_password_hash", sa.String(length=128), nullable=True),
    )
    op.drop_column("users", "phone")

    # --- Files: attachable to plans / assessments / assignments / reports ---
    for column, table in (
        ("lesson_plan_id", "lesson_plans"),
        ("assessment_id", "assessments"),
        ("assignment_id", "assignments"),
        ("report_id", "reports"),
    ):
        op.add_column(
            "files",
            sa.Column(column, postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            op.f(f"fk_files_{column}_{table}"),
            "files",
            table,
            [column],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            f"ix_files_{column.removesuffix('_id')}",
            "files",
            [column],
            postgresql_where=sa.text(f"{column} IS NOT NULL"),
        )

    # --- Reports: class + period requisites ----------------------------------
    op.add_column(
        "reports",
        sa.Column(
            "class_name", sa.String(length=64), nullable=False, server_default=""
        ),
    )
    op.add_column(
        "reports",
        sa.Column("period", sa.String(length=120), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("reports", "period")
    op.drop_column("reports", "class_name")

    for column, table in (
        ("lesson_plan_id", "lesson_plans"),
        ("assessment_id", "assessments"),
        ("assignment_id", "assignments"),
        ("report_id", "reports"),
    ):
        op.drop_index(f"ix_files_{column.removesuffix('_id')}", table_name="files")
        op.drop_constraint(op.f(f"fk_files_{column}_{table}"), "files", type_="foreignkey")
        op.drop_column("files", column)

    op.add_column(
        "users",
        sa.Column("phone", sa.String(length=15), nullable=True),
    )
    op.drop_column("users", "safe_password_hash")
