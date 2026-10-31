"""Create the tables of the storage layer

Revision ID: dfaaec79ecb1
Revises: 
Create Date: 2026-10-24 01:46:21.217623

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import libs.storage.sql.tables

# revision identifiers, used by Alembic.
revision: str = "dfaaec79ecb1"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "auth_app_tokens",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("project_id", sa.String(length=24), nullable=True),
        sa.Column("lifespan_seconds", sa.Float(), nullable=True),
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("token", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(length=24), nullable=True),
        sa.Column(
            "created_at",
            libs.storage.sql.tables.UtcDateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("token", name="ux_auth_app_tokens_token"),
    )
    op.create_index(
        "ix_auth_app_tokens_project_id_user_id",
        "auth_app_tokens",
        ["project_id", "user_id"],
        unique=False,
    )
    op.create_table(
        "auth_projects",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("qpu_seconds", sa.Float(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("admin_id", sa.String(length=24), nullable=True),
        sa.Column("is_personal", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("name", name="ux_auth_projects_name"),
    )
    op.create_table(
        "calibrations",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("qubits", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("resonators", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("couplers", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("discriminators", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("last_calibrated", sa.String(), nullable=True),
        sa.Column("id", sa.String(length=24), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "calibrations_logs",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("qubits", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("resonators", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("couplers", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("discriminators", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("last_calibrated", sa.String(), nullable=True),
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_calibrations_logs_last_calibrated",
        "calibrations_logs",
        [sa.literal_column("last_calibrated DESC")],
        unique=False,
    )
    op.create_index(
        "ix_calibrations_logs_name", "calibrations_logs", ["name"], unique=False
    )
    op.create_table(
        "deleted_auth_projects",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("qpu_seconds", sa.Float(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("user_ids", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("admin_id", sa.String(length=24), nullable=True),
        sa.Column("is_personal", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("id"),
    )
    op.create_table(
        "devices",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("number_of_qubits", sa.BigInteger(), nullable=True),
        sa.Column("last_online", sa.String(), nullable=True),
        sa.Column("is_online", sa.Boolean(), nullable=True),
        sa.Column("basis_gates", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("coupling_map", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("coordinates", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("is_simulator", sa.Boolean(), nullable=True),
        sa.Column("coupling_dict", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("characterized", sa.Boolean(), nullable=True),
        sa.Column("open_pulse", sa.Boolean(), nullable=True),
        sa.Column("meas_map", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("number_of_couplers", sa.BigInteger(), nullable=True),
        sa.Column("number_of_resonators", sa.BigInteger(), nullable=True),
        sa.Column("dt", sa.Float(), nullable=True),
        sa.Column("dtm", sa.Float(), nullable=True),
        sa.Column("qubit_ids", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("meas_lo_freq", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("qubit_lo_freq", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("gates", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("qubit_ids_coupler_map", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("id", sa.String(length=24), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "jobs",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("device", sa.String(), nullable=True),
        sa.Column("calibration_date", sa.String(), nullable=True),
        sa.Column("id", sa.String(length=24), nullable=True),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(length=24), nullable=True),
        sa.Column("user_id", sa.String(length=24), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("cancellation_reason", sa.String(), nullable=True),
        sa.Column("timestamps", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("download_url", sa.String(), nullable=True),
        sa.Column("result", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("estimated_duration", sa.Float(), nullable=True),
        sa.Column("actual_duration", sa.Float(), nullable=True),
        sa.Column("access_token", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_table(
        "notice_preferences",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("id", sa.String(length=24), nullable=True),
        sa.Column("user_id", sa.String(length=24), nullable=False),
        sa.Column("email_prefs", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "notice_templates",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("id", sa.String(length=24), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("body", sa.String(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("context_cls_path", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("type"),
    )
    op.create_table(
        "notices",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("body", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(length=24), nullable=True),
        sa.Column("created_by", sa.String(length=24), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("ref_type", sa.String(), nullable=True),
        sa.Column("ref_id", sa.String(length=24), nullable=True),
        sa.Column("context", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("email_status", sa.String(), nullable=True),
        sa.Column("email_attempts", sa.BigInteger(), nullable=True),
        sa.Column("read_at", sa.String(), nullable=True),
        sa.Column(
            "starts_at",
            libs.storage.sql.tables.UtcDateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            libs.storage.sql.tables.UtcDateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_notices_email_status_updated_at",
        "notices",
        ["email_status", "updated_at"],
        unique=False,
    )
    op.create_index("ix_notices_expires_at", "notices", ["expires_at"], unique=False)
    op.create_index(
        "ix_notices_ref_type_ref_id", "notices", ["ref_type", "ref_id"], unique=False
    )
    op.create_index(
        "ix_notices_starts_at_expires_at",
        "notices",
        ["starts_at", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_notices_user_id_created_at",
        "notices",
        ["user_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_notices_user_id_read_at", "notices", ["user_id", "read_at"], unique=False
    )
    op.create_table(
        "requests",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("resource_id", sa.String(length=24), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("requester_id", sa.String(length=24), nullable=True),
        sa.Column("requester_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("approver_id", sa.String(length=24), nullable=True),
        sa.Column("approver_name", sa.String(), nullable=True),
        sa.Column("rejection_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_requests_requester_id_created_at",
        "requests",
        ["requester_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_requests_resource_id_status",
        "requests",
        ["resource_id", "status"],
        unique=False,
    )
    op.create_index("ix_requests_type", "requests", ["type"], unique=False)
    op.create_table(
        "auth_project_user_ids",
        sa.Column("auth_project_id", sa.String(length=24), nullable=False),
        sa.Column("user_id", sa.String(length=24), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["auth_project_id"], ["auth_projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("auth_project_id", "user_id"),
    )
    op.create_index(
        "ix_auth_project_user_ids_user_id",
        "auth_project_user_ids",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "notice_dismissed_by",
        sa.Column("notice_id", sa.String(length=24), nullable=False),
        sa.Column("dismissed_by", sa.String(length=24), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["notice_id"], ["notices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("notice_id", "dismissed_by"),
    )
    op.create_index(
        "ix_notice_dismissed_by_dismissed_by",
        "notice_dismissed_by",
        ["dismissed_by"],
        unique=False,
    )
    op.create_table(
        "request_target_user_ids",
        sa.Column("request_id", sa.String(length=24), nullable=False),
        sa.Column("target_user_id", sa.String(length=24), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("request_id", "target_user_id"),
    )
    op.create_index(
        "ix_request_target_user_ids_target_user_id",
        "request_target_user_ids",
        ["target_user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_request_target_user_ids_target_user_id",
        table_name="request_target_user_ids",
    )
    op.drop_table("request_target_user_ids")
    op.drop_index(
        "ix_notice_dismissed_by_dismissed_by", table_name="notice_dismissed_by"
    )
    op.drop_table("notice_dismissed_by")
    op.drop_index(
        "ix_auth_project_user_ids_user_id", table_name="auth_project_user_ids"
    )
    op.drop_table("auth_project_user_ids")
    op.drop_index("ix_requests_type", table_name="requests")
    op.drop_index("ix_requests_resource_id_status", table_name="requests")
    op.drop_index("ix_requests_requester_id_created_at", table_name="requests")
    op.drop_table("requests")
    op.drop_index("ix_notices_user_id_read_at", table_name="notices")
    op.drop_index("ix_notices_user_id_created_at", table_name="notices")
    op.drop_index("ix_notices_starts_at_expires_at", table_name="notices")
    op.drop_index("ix_notices_ref_type_ref_id", table_name="notices")
    op.drop_index("ix_notices_expires_at", table_name="notices")
    op.drop_index("ix_notices_email_status_updated_at", table_name="notices")
    op.drop_table("notices")
    op.drop_table("notice_templates")
    op.drop_table("notice_preferences")
    op.drop_table("jobs")
    op.drop_table("devices")
    op.drop_table("deleted_auth_projects")
    op.drop_index("ix_calibrations_logs_name", table_name="calibrations_logs")
    op.drop_index(
        "ix_calibrations_logs_last_calibrated", table_name="calibrations_logs"
    )
    op.drop_table("calibrations_logs")
    op.drop_table("calibrations")
    op.drop_table("auth_projects")
    op.drop_index("ix_auth_app_tokens_project_id_user_id", table_name="auth_app_tokens")
    op.drop_table("auth_app_tokens")
