"""Store the devices' connections and switch

Revision ID: a86487b30732
Revises: 01f3a918b5dd
Create Date: 2026-10-30 21:49:22.093103

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import libs.storage.sql.tables

# revision identifiers, used by Alembic.
revision: str = "a86487b30732"
down_revision: Union[str, Sequence[str], None] = "01f3a918b5dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "device_connections",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("device_name", sa.String(), nullable=True),
        sa.Column(
            "connected_at",
            libs.storage.sql.tables.UtcDateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            libs.storage.sql.tables.UtcDateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("id"),
    )
    with op.batch_alter_table("device_connections", schema=None) as batch_op:
        batch_op.create_index(
            "ix_device_connections_device_name", ["device_name"], unique=False
        )
        batch_op.create_index(
            "ix_device_connections_expires_at", ["expires_at"], unique=False
        )

    op.create_table(
        "switched_off_devices",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "switched_off_at",
            libs.storage.sql.tables.UtcDateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("switched_off_devices")
    with op.batch_alter_table("device_connections", schema=None) as batch_op:
        batch_op.drop_index("ix_device_connections_expires_at")
        batch_op.drop_index("ix_device_connections_device_name")

    op.drop_table("device_connections")
