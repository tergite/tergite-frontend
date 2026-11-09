"""Store the pulse limits of devices

Revision ID: 5d1c0e7a9b42
Revises: 94e5d29ed867
Create Date: 2026-11-09 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d1c0e7a9b42"
down_revision: Union[str, Sequence[str], None] = "94e5d29ed867"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: devices may carry the limits of their pulse-level jobs"""
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("pulse_limits", sa.JSON(none_as_null=True), nullable=True)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_column("pulse_limits")
