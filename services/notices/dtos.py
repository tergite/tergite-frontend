# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Data Transfer Objects for the notices service"""
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Dict, List, NamedTuple, Optional, Self, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)

from libs.storage import Database, Id, Schema, StorageSpec, generate_id
from utils.date_time import datetime_to_zulu, get_current_timestamp, get_utc_now

NOTICE_DB_COLLECTION = "notices"
NOTICE_PREFS_DB_COLLECTION = "notice_preferences"
TEMPLATE_DB_COLLECTION = "notice_templates"


class RefType(str, Enum):
    """The type of references that a notice can refer to"""

    USER_REQUEST = "user_request"
    PROJECT = "project"


class EmailStatus(str, Enum):
    """Delivery state of the email copy of a notice.

    The notice row doubles as the email outbox, so this is what the sweeper reads.
    """

    NOT_APPLICABLE = "not-applicable"
    PENDING = "pending"
    # claimed by the process sending it
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


class NoticeSeverity(int, Enum):
    """How urgent a notice is; the most urgent is the lowest, so notices sort by it"""

    CRITICAL = 1
    WARNING = 2
    INFO = 3


class BaseNoticeContext(BaseModel):
    """The base class for the context passed to the notice template."""

    model_config = ConfigDict(extra="allow")


class ProjectRequestContext(BaseNoticeContext):
    """The context passed to the notice template when anything is requested about a project."""

    requester_name: str = ""
    project_id: str = ""
    project_name: str = ""
    reason: str = ""
    approver_name: str = ""
    seconds: int | float | str = ""
    admin_email: str = ""


class CustomNoticeContext(BaseNoticeContext):
    """The context for custom notices."""

    title: str = ""
    body: str = ""


class NoticeTypeId(StrEnum):
    """The kinds of notices"""

    PROJECT_ACCESS_REQUESTED = "project-access-requested"
    PROJECT_ACCESS_APPROVED = "project-access-approved"
    PROJECT_ACCESS_REJECTED = "project-access-rejected"
    PROJECT_CREATE_REQUESTED = "project-create-requested"
    PROJECT_CREATE_APPROVED = "project-create-approved"
    PROJECT_CREATE_REJECTED = "project-create-rejected"
    PROJECT_CLOSE_REQUESTED = "project-close-requested"
    PROJECT_CLOSE_APPROVED = "project-close-approved"
    PROJECT_CLOSE_REJECTED = "project-close-rejected"
    PROJECT_TRANSFER_REQUESTED = "project-transfer-requested"
    PROJECT_TRANSFER_APPROVED = "project-transfer-approved"
    PROJECT_TRANSFER_REJECTED = "project-transfer-rejected"
    QPU_SECONDS_REQUESTED = "qpu-seconds-requested"
    QPU_SECONDS_GRANTED = "qpu-seconds-granted"
    QPU_SECONDS_DENIED = "qpu-seconds-denied"
    QPU_SECONDS_LOW = "qpu-seconds-low"
    QPU_SECONDS_DEPLETED = "qpu-seconds-depleted"
    PULSE_ACCESS_REQUESTED = "pulse-access-requested"
    PULSE_ACCESS_GRANTED = "pulse-access-granted"
    PULSE_ACCESS_DENIED = "pulse-access-denied"
    PROJECT_MEMBERSHIP_GRANTED = "project-membership-granted"
    PROJECT_MEMBERSHIP_REVOKED = "project-membership-revoked"
    PROJECT_ADMIN_ASSIGNED = "project-admin-assigned"
    CUSTOM = "custom"
    CUSTOM_BROADCAST = "custom-broadcast"


class NoticeTypeInfo(NamedTuple):
    """The default template of a kind of notice"""

    title: str
    body: str
    severity: NoticeSeverity


NOTICE_TYPE_INFO: Dict[NoticeTypeId, NoticeTypeInfo] = {
    NoticeTypeId.PROJECT_ACCESS_REQUESTED: NoticeTypeInfo(
        title="Access request for {project_name}",
        body="{requester_name} is asking to join {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PROJECT_ACCESS_APPROVED: NoticeTypeInfo(
        title="You were added to {project_name}",
        body="{approver_name} approved your request to join {project_name}.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PROJECT_ACCESS_REJECTED: NoticeTypeInfo(
        title="Access to {project_name} was declined",
        body="{approver_name} declined your request to join {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeTypeId.PROJECT_CREATE_REQUESTED: NoticeTypeInfo(
        title="Create request for {project_name}",
        body="{requester_name} is asking to create {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PROJECT_CREATE_APPROVED: NoticeTypeInfo(
        title="Your project {project_name} was created",
        body="{approver_name} approved your request to create {project_name}.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PROJECT_CREATE_REJECTED: NoticeTypeInfo(
        title="Project {project_name} was declined",
        body="{approver_name} declined your request to create {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeTypeId.PROJECT_CLOSE_REQUESTED: NoticeTypeInfo(
        title="Deletion request for {project_name}",
        body="{requester_name} is asking to close {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PROJECT_CLOSE_APPROVED: NoticeTypeInfo(
        title="Your project {project_name} was closed",
        body="{approver_name} approved your request to close {project_name}.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PROJECT_CLOSE_REJECTED: NoticeTypeInfo(
        title="Deletion of project {project_name} was declined",
        body="{approver_name} declined your request to close {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeTypeId.PROJECT_TRANSFER_REQUESTED: NoticeTypeInfo(
        title="Transfer request for {project_name}",
        body="{requester_name} is asking to transfer {project_name} to {admin_email}: {reason}",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PROJECT_TRANSFER_APPROVED: NoticeTypeInfo(
        title="Project {project_name} was transferred",
        body="{approver_name} approved {requester_name}'s request to transfer {project_name} to {admin_email}.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PROJECT_TRANSFER_REJECTED: NoticeTypeInfo(
        title="Transfer of project {project_name} was declined",
        body="{approver_name} declined your request to transfer {project_name} to {admin_email}. {reason}",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeTypeId.QPU_SECONDS_REQUESTED: NoticeTypeInfo(
        title="QPU time request for {project_name}",
        body="{requester_name} is asking for {seconds}s on {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.QPU_SECONDS_GRANTED: NoticeTypeInfo(
        title="{seconds}s of QPU time added to {project_name}",
        body="{approver_name} granted {seconds}s of QPU time on {project_name}.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.QPU_SECONDS_DENIED: NoticeTypeInfo(
        title="QPU time for {project_name} was declined",
        body="{approver_name} declined the QPU time request for {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeTypeId.QPU_SECONDS_LOW: NoticeTypeInfo(
        title="{project_name} is running low on QPU time",
        body="{project_name} has {seconds}s of QPU time left. Request more before it runs out.",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeTypeId.QPU_SECONDS_DEPLETED: NoticeTypeInfo(
        title="{project_name} is out of QPU time",
        body="{project_name} has no QPU time left, so its jobs will be rejected until more is granted.",
        severity=NoticeSeverity.CRITICAL,
    ),
    NoticeTypeId.PULSE_ACCESS_REQUESTED: NoticeTypeInfo(
        title="Pulse-level jobs request for {project_name}",
        body="{requester_name} is asking for pulse-level jobs on {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PULSE_ACCESS_GRANTED: NoticeTypeInfo(
        title="Pulse-level jobs allowed on {project_name}",
        body="{approver_name} allowed pulse-level jobs on {project_name}. Each device runs them within its own limits.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PULSE_ACCESS_DENIED: NoticeTypeInfo(
        title="Pulse-level jobs for {project_name} were declined",
        body="{approver_name} declined the request for pulse-level jobs on {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeTypeId.PROJECT_MEMBERSHIP_GRANTED: NoticeTypeInfo(
        title="You were added to {project_name}",
        body="{approver_name} added you to {project_name} ({project_id}). You can now create API tokens for it.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.PROJECT_MEMBERSHIP_REVOKED: NoticeTypeInfo(
        title="You were removed from {project_name}",
        body="{approver_name} removed you from {project_name}. Any API tokens you held for it no longer work.",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeTypeId.PROJECT_ADMIN_ASSIGNED: NoticeTypeInfo(
        title="You now administer {project_name}",
        body="{approver_name} made you the admin of {project_name} ({project_id}). Requests to join it come to you.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.CUSTOM: NoticeTypeInfo(
        title="{title}",
        body="{body}",
        # FIXME: severity depends on the author of the notice. See this as a default.
        severity=NoticeSeverity.INFO,
    ),
    NoticeTypeId.CUSTOM_BROADCAST: NoticeTypeInfo(
        title="{title}",
        body="{body}",
        # FIXME: severity depends on the author of the notice. See this as a default.
        severity=NoticeSeverity.INFO,
    ),
}


class Notice(Schema):
    """A message"""

    __storage__ = StorageSpec(
        table=NOTICE_DB_COLLECTION,
        expires="expires_at",
        indexed_lists=("dismissed_by",),
        indexes=(
            ("user_id", "-created_at"),
            ("user_id", "read_at"),
            ("email_status", "updated_at"),
            ("starts_at", "expires_at"),
            ("ref_type", "ref_id"),
        ),
        should_skip_invalid=True,
    )
    model_config = ConfigDict(extra="ignore")

    id: Id = Field(default_factory=generate_id)

    type: NoticeTypeId
    title: str
    body: str
    user_id: Optional[Id] = None
    # 'created_by' is specific to custom notices
    created_by: Optional[Id] = None
    severity: NoticeSeverity = NoticeSeverity.INFO
    ref_type: Optional[RefType] = None
    ref_id: Optional[Id] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    email_status: EmailStatus = EmailStatus.NOT_APPLICABLE
    email_attempts: int = 0
    # read_at and dismissed_by must be atomically set for non-broadcast messages
    read_at: Optional[str] = None
    dismissed_by: List[Id] = Field(default_factory=list)
    starts_at: Optional[datetime] = None
    # kept bounded by a TTL index rather than manual pruning
    expires_at: Optional[datetime] = None
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    @field_serializer(
        "expires_at", "starts_at", "created_at", "updated_at", when_used="json"
    )
    def serialize_date_fields(self, value: Optional[datetime]) -> Optional[str]:
        """Convert datetime value to string when working with JSON

        Args:
            value: the date field's value

        Returns:
            the value as a Zulu timestamp, or as it is if not a datetime
        """
        try:
            return datetime_to_zulu(value)
        except AttributeError:
            return value

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validates the notice record

        For example:
            - 'created_by' cannot be None if 'type' of notice is custom
            - 'user_id' cannot be None if 'type' is not custom-broadcast
            - 'user_id' must be None if 'type' is custom-broadcast
            - if 'read_at' is set then the 'dismissed_by' field must include the 'user_id' if type is not custom-broadcast
            - 'read_at' must be None if 'type' is custom-broadcast

        Returns:
            the notice, once valid

        Raises:
            ValueError: the notice breaks one of the rules above
        """
        custom_kind = NoticeTypeId.CUSTOM
        custom_broadcast_kind = NoticeTypeId.CUSTOM_BROADCAST

        if self.created_by is None and self.type == custom_kind:
            raise ValueError("Custom notice cannot be created by no one")
        if self.type == custom_broadcast_kind:
            if self.user_id:
                raise ValueError(
                    "Custom broadcast notices should not have target users"
                )
            if self.read_at:
                raise ValueError("Custom broadcast notices can not have read_at set")
        else:
            if self.user_id is None:
                raise ValueError("Non-broadcast notices should have target users")
            if self.read_at and (
                not self.dismissed_by or self.user_id not in self.dismissed_by
            ):
                raise ValueError(
                    "Non-broadcast notices when read must also append user_id to dismissed_by"
                )

        return self

    @classmethod
    def from_template(
        cls, template: "NoticeTemplate", context: BaseNoticeContext, **fields: Any
    ) -> Self:
        """Constructs a notice from a template, its title and body filled in from the context

        Args:
            template: The notice template
            context: The values the template's title and body are formatted with
            fields: Additional fields of the notice

        Returns:
            the notice
        """
        values = context.model_dump()
        return cls.model_validate(
            {
                **template.model_dump(exclude={"id"}),
                "title": template.title.format_map(values),
                "body": template.body.format_map(values),
                **fields,
            }
        )


class NoticeQuery(BaseModel):
    """The constraints of a query of notices

    A notice is read by a user when it holds their id in dismissed_by.
    """

    # the user whose notices, direct or broadcast, are wanted; None for anyone's
    user_id: Optional[Id] = None
    min_start_utc: Optional[datetime] = None
    max_start_utc: Optional[datetime] = None
    min_expires_utc: Optional[datetime] = None
    max_expires_utc: Optional[datetime] = None
    should_include_dismissed: bool = False
    # None or empty for any
    types: Optional[Sequence[NoticeTypeId]] = None
    # None for either
    is_read: Optional[bool] = None


class NoticePreferences(Schema):
    """One user's opt-outs, owned by this service rather than by the auth service"""

    __storage__ = StorageSpec(
        table=NOTICE_PREFS_DB_COLLECTION, key="user_id", unique=("user_id",)
    )

    id: Id = Field(default_factory=generate_id)
    user_id: Id
    email_prefs: Dict[NoticeTypeId, bool] = Field(default_factory=dict)
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)


class NoticeTemplate(Schema):
    """The templates for each notice type persisted and updated in the database"""

    __storage__ = StorageSpec(
        table=TEMPLATE_DB_COLLECTION, key="type", unique=("type",)
    )

    id: Id = Field(default_factory=generate_id)
    type: NoticeTypeId
    title: str
    body: str
    severity: NoticeSeverity

    @classmethod
    def from_notice_type(cls, type_id: NoticeTypeId) -> Self:
        """Converts a notice type's default template to a template document

        Args:
            type_id: the notice type

        Returns:
            the notice type's default template
        """
        info = NOTICE_TYPE_INFO[type_id]
        return cls(
            type=type_id, title=info.title, body=info.body, severity=info.severity
        )


class CustomNoticeCreate(BaseModel):
    """The schema for creating custom notices"""

    message: str
    severity: NoticeSeverity
    expires_at: datetime = Field(default_factory=get_utc_now)
    starts_at: datetime = Field(default_factory=get_utc_now)
    target_user_emails: Optional[List[str]] = None

    async def to_documents(self, database: Database, created_by: str) -> List[Notice]:
        """Converts the creation request to a notice for each target user, or one broadcast

        Args:
            database: the database where the users and notice templates are stored
            created_by: the id of the user publishing the notice

        Returns:
            a notice for each target user found, or a single broadcast if there are none
        """
        # imported here to avoid a circular import, as the auth service imports this one
        from services.auth import User

        context = CustomNoticeContext(title=self.message, body=self.message)
        fields = dict(
            severity=self.severity,
            expires_at=self.expires_at,
            starts_at=self.starts_at,
            created_by=created_by,
        )
        if self.target_user_emails:
            users = await database.find(
                User, filter={"email": {"$in": self.target_user_emails}}
            )
            template = await database.get(NoticeTemplate, NoticeTypeId.CUSTOM)
            return [
                Notice.from_template(
                    template, context=context, user_id=user.id, **fields
                )
                for user in users
            ]

        template = await database.get(NoticeTemplate, NoticeTypeId.CUSTOM_BROADCAST)
        return [Notice.from_template(template, context=context, **fields)]
