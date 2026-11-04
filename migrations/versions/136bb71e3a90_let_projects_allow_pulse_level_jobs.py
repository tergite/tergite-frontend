"""Let projects allow pulse-level jobs

Revision ID: 136bb71e3a90
Revises: c001c281888c
Create Date: 2026-11-03 14:42:47.738310

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "136bb71e3a90"
down_revision: Union[str, Sequence[str], None] = "c001c281888c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("auth_projects", "deleted_auth_projects")


def upgrade() -> None:
    """Upgrade schema: projects may allow pulse-level jobs, which none already there does"""
    for table in _TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("is_pulse_allowed", sa.Boolean(), nullable=True)
            )
        op.execute(sa.text(f"UPDATE {table} SET is_pulse_allowed = false"))


def downgrade() -> None:
    """Downgrade schema."""
    for table in reversed(_TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("is_pulse_allowed")
