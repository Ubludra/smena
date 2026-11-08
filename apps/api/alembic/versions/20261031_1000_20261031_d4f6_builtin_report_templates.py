"""templates: built-in report skeletons (system templates)

Revision ID: 20261031_d4f6
Revises: 20261031_c3e5
Create Date: 2026-10-31

owner_id becomes NULLable: NULL marks a built-in system template — readable
by every teacher, mutable by none. entity_type gains "report" (payload =
MaterialCreate shape: using one pre-fills the material form). Five real
Russian school report skeletons are seeded from the single source in
smena_api.services.builtin_reports; every one is a form of a LOCAL act of
the school (Order No. 779 of 06.11.2024 fixed the federal mandatory list).
"""

import uuid

import sqlalchemy as sa
from alembic import op

from smena_api.services.builtin_reports import BUILTIN_REPORT_TEMPLATES, seed_builtin

revision = "20261031_d4f6"
down_revision = "20261031_c3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_templates_entity_type_known", "templates", type_="check")
    op.alter_column("templates", "owner_id", existing_type=sa.UUID(), nullable=True)
    op.create_check_constraint(
        "ck_templates_entity_type_known",
        "templates",
        "entity_type IN ('lesson_plan', 'assignment', 'assessment', 'report')",
    )
    seed_builtin(op.get_bind())


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM templates WHERE id::text = ANY(:ids)").bindparams(
            ids=[str(uuid.UUID(row["id"])) for row in BUILTIN_REPORT_TEMPLATES]
        )
    )
    op.drop_constraint("ck_templates_entity_type_known", "templates", type_="check")
    op.alter_column("templates", "owner_id", existing_type=sa.UUID(), nullable=False)
    op.create_check_constraint(
        "ck_templates_entity_type_known",
        "templates",
        "entity_type IN ('lesson_plan', 'assignment', 'assessment')",
    )
