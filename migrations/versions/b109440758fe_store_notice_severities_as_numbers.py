"""Store notice severities as numbers

Revision ID: b109440758fe
Revises: 642c27451000
Create Date: 2026-10-24 13:30:42.873895

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b109440758fe"
down_revision: Union[str, Sequence[str], None] = "642c27451000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NAMES_TO_DIGITS = (
    "CASE severity WHEN 'critical' THEN '1' WHEN 'warning' THEN '2' ELSE '3' END"
)
_DIGITS_TO_NAMES = (
    "CASE severity WHEN '1' THEN 'critical' WHEN '2' THEN 'warning' ELSE 'info' END"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(f"UPDATE notice_templates SET severity = {_NAMES_TO_DIGITS}")
    op.execute(f"UPDATE notices SET severity = {_NAMES_TO_DIGITS}")

    with op.batch_alter_table("notice_templates", schema=None) as batch_op:
        batch_op.alter_column(
            "severity",
            existing_type=sa.VARCHAR(),
            type_=sa.BigInteger(),
            existing_nullable=True,
            postgresql_using="severity::bigint",
        )

    with op.batch_alter_table("notices", schema=None) as batch_op:
        batch_op.alter_column(
            "severity",
            existing_type=sa.VARCHAR(),
            type_=sa.BigInteger(),
            existing_nullable=True,
            postgresql_using="severity::bigint",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("notices", schema=None) as batch_op:
        batch_op.alter_column(
            "severity",
            existing_type=sa.BigInteger(),
            type_=sa.VARCHAR(),
            existing_nullable=True,
        )

    with op.batch_alter_table("notice_templates", schema=None) as batch_op:
        batch_op.alter_column(
            "severity",
            existing_type=sa.BigInteger(),
            type_=sa.VARCHAR(),
            existing_nullable=True,
        )

    op.execute(f"UPDATE notices SET severity = {_DIGITS_TO_NAMES}")
    op.execute(f"UPDATE notice_templates SET severity = {_DIGITS_TO_NAMES}")
