"""Keep the source of jobs submitted from the dashboard

Revision ID: 94e5d29ed867
Revises: 221e28f138bc
Create Date: 2026-11-06 15:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "94e5d29ed867"
down_revision: Union[str, Sequence[str], None] = "221e28f138bc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: a job may carry the circuits and settings it was submitted with"""
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.JSON(none_as_null=True), nullable=True)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_column("source")
