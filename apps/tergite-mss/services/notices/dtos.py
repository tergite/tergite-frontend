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
from enum import Enum
from typing import Any, Dict, List, Literal, NamedTuple, Optional, Self, Type, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from libs.storage import Database, Id, Schema, StorageSpec, generate_id
from utils.date_time import datetime_to_zulu, get_current_timestamp, get_utc_now
from utils.types import get_class_import_path, load_class

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


class NoticeTypeInfo(NamedTuple):
    id: str
    title: str
    body: str
    severity: NoticeSeverity
    context_cls: Type[BaseNoticeContext] = BaseNoticeContext


class NoticeType(NoticeTypeInfo, Enum):
    """The kinds of notices plus their associated data"""

    PROJECT_ACCESS_REQUESTED = NoticeTypeInfo(
        id="project-access-requested",
        title="Access request for {project_name}",
        body="{requester_name} is asking to join {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    PROJECT_ACCESS_APPROVED = NoticeTypeInfo(
        id="project-access-approved",
        title="You were added to {project_name}",
        body="{approver_name} approved your request to join {project_name}.",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    PROJECT_ACCESS_REJECTED = NoticeTypeInfo(
        id="project-access-rejected",
        title="Access to {project_name} was declined",
        body="{approver_name} declined your request to join {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
        context_cls=ProjectRequestContext,
    )
    PROJECT_CREATE_REQUESTED = NoticeTypeInfo(
        id="project-create-requested",
        title="Create request for {project_name}",
        body="{requester_name} is asking to create {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    PROJECT_CREATE_APPROVED = NoticeTypeInfo(
        id="project-create-approved",
        title="Your project {project_name} was created",
        body="{approver_name} approved your request to create {project_name}.",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    PROJECT_CREATE_REJECTED = NoticeTypeInfo(
        id="project-create-rejected",
        title="Project {project_name} was declined",
        body="{approver_name} declined your request to create {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
        context_cls=ProjectRequestContext,
    )
    PROJECT_CLOSE_REQUESTED = NoticeTypeInfo(
        id="project-close-requested",
        title="Deletion request for {project_name}",
        body="{requester_name} is asking to close {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    PROJECT_CLOSE_APPROVED = NoticeTypeInfo(
        id="project-close-approved",
        title="Your project {project_name} was closed",
        body="{approver_name} approved your request to close {project_name}.",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    PROJECT_CLOSE_REJECTED = NoticeTypeInfo(
        id="project-close-rejected",
        title="Deletion of project {project_name} was declined",
        body="{approver_name} declined your request to close {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
        context_cls=ProjectRequestContext,
    )
    PROJECT_TRANSFER_REQUESTED = NoticeTypeInfo(
        id="project-transfer-requested",
        title="Transfer request for {project_name}",
        body="{requester_name} is asking to transfer {project_name} to {admin_email}: {reason}",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    PROJECT_TRANSFER_APPROVED = NoticeTypeInfo(
        id="project-transfer-approved",
        title="Project {project_name} was transferred",
        body="{approver_name} approved {requester_name}'s request to transfer {project_name} to {admin_email}.",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    PROJECT_TRANSFER_REJECTED = NoticeTypeInfo(
        id="project-transfer-rejected",
        title="Transfer of project {project_name} was declined",
        body="{approver_name} declined your request to transfer {project_name} to {admin_email}. {reason}",
        severity=NoticeSeverity.WARNING,
        context_cls=ProjectRequestContext,
    )
    QPU_SECONDS_REQUESTED = NoticeTypeInfo(
        id="qpu-seconds-requested",
        title="QPU time request for {project_name}",
        body="{requester_name} is asking for {seconds}s on {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    QPU_SECONDS_GRANTED = NoticeTypeInfo(
        id="qpu-seconds-granted",
        title="{seconds}s of QPU time added to {project_name}",
        body="{approver_name} granted {seconds}s of QPU time on {project_name}.",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    QPU_SECONDS_DENIED = NoticeTypeInfo(
        id="qpu-seconds-denied",
        title="QPU time for {project_name} was declined",
        body="{approver_name} declined the QPU time request for {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
        context_cls=ProjectRequestContext,
    )
    QPU_SECONDS_LOW = NoticeTypeInfo(
        id="qpu-seconds-low",
        title="{project_name} is running low on QPU time",
        body="{project_name} has {seconds}s of QPU time left. Request more before it runs out.",
        severity=NoticeSeverity.WARNING,
        context_cls=ProjectRequestContext,
    )
    QPU_SECONDS_DEPLETED = NoticeTypeInfo(
        id="qpu-seconds-depleted",
        title="{project_name} is out of QPU time",
        body="{project_name} has no QPU time left, so its jobs will be rejected until more is granted.",
        severity=NoticeSeverity.CRITICAL,
        context_cls=ProjectRequestContext,
    )
    PROJECT_MEMBERSHIP_GRANTED = NoticeTypeInfo(
        id="project-membership-granted",
        title="You were added to {project_name}",
        body="{approver_name} added you to {project_name} ({project_id}). You can now create API tokens for it.",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    PROJECT_MEMBERSHIP_REVOKED = NoticeTypeInfo(
        id="project-membership-revoked",
        title="You were removed from {project_name}",
        body="{approver_name} removed you from {project_name}. Any API tokens you held for it no longer work.",
        severity=NoticeSeverity.WARNING,
        context_cls=ProjectRequestContext,
    )
    PROJECT_ADMIN_ASSIGNED = NoticeTypeInfo(
        id="project-admin-assigned",
        title="You now administer {project_name}",
        body="{approver_name} made you the admin of {project_name} ({project_id}). Requests to join it come to you.",
        severity=NoticeSeverity.INFO,
        context_cls=ProjectRequestContext,
    )
    CUSTOM = NoticeTypeInfo(
        id="custom",
        title="{title}",
        body="{body}",
        # FIXME: severity depends on the author of the notice. See this as a default.
        severity=NoticeSeverity.INFO,
        context_cls=CustomNoticeContext,
    )
    CUSTOM_BROADCAST = NoticeTypeInfo(
        id="custom-broadcast",
        title="{title}",
        body="{body}",
        # FIXME: severity depends on the author of the notice. See this as a default.
        severity=NoticeSeverity.INFO,
        context_cls=CustomNoticeContext,
    )

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Gets the NoticeTypeEnum from a string.

        Raises:
            KeyError: if the string is not a valid notice type.
        """
        for notice_type in cls:
            if notice_type.id == value:
                return notice_type
        raise KeyError(value)

    def __str__(self):
        return self.id


type NoticeTypeId = Literal[tuple(v.id for v in NoticeType)]  # type: ignore[valid-type]
"""A kind of NoticeTypes"""
# FIXME: Maybe find a stronger type for the strings in Notice type or just setup a map of dict[NoticeType, NoticeInfo]


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
        """Convert datetime value to string when working with JSON"""
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

        """
        custom_kind = NoticeType.CUSTOM.id
        custom_broadcast_kind = NoticeType.CUSTOM_BROADCAST.id

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
        cls,
        template: "NoticeTemplate",
        context: Optional[BaseNoticeContext] = None,
        **kwargs,
    ) -> Self:
        """Constructs a notice from a template

        Args:
            template: The notice template
            context: The notice context useful for formating the template;
                defaults to the template's context class with its defaults
            kwargs: Additional arguments passed to the notice constructor

        Returns:
            The notice object
        """
        # formatted here as validating a record passes no context along
        values = (context or template.context_cls()).model_dump()
        data = {
            **template.model_dump(exclude={"id"}),
            "title": template.title.format_map(values),
            "body": template.body.format_map(values),
            **kwargs,
        }
        return cls.model_validate(data)


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
    context_cls_path: str = get_class_import_path(BaseNoticeContext)

    __context_cls: Optional[Type[BaseNoticeContext]] = None

    @property
    def context_cls(self) -> Type[BaseNoticeContext]:
        """The context class for this template"""
        if self.__context_cls is None:
            self.__context_cls = cast(
                Type[BaseNoticeContext], load_class(self.context_cls_path)
            )
        return self.__context_cls

    @field_validator("context_cls_path", mode="before")
    @classmethod
    def validate_context_cls(cls, value: Any):
        """Convert object fields to string always"""
        if isinstance(value, type):
            return get_class_import_path(value)
        return value

    @classmethod
    def from_notice_type(cls, value: NoticeType | str) -> Self:
        """Converts a notice type to a notice template document."""
        if isinstance(value, str):
            value = NoticeType.from_str(value)

        return cls(
            type=value.id,
            title=value.title,
            body=value.body,
            severity=value.severity,
            context_cls_path=get_class_import_path(value.context_cls),
        )


class CustomNoticeCreate(BaseModel):
    """The schema for creating custom notices"""

    message: str
    severity: NoticeSeverity
    expires_at: datetime = Field(default_factory=get_utc_now)
    starts_at: datetime = Field(default_factory=get_utc_now)
    target_user_emails: Optional[List[str]] = None

    async def to_documents(self, database: Database, **kwargs: Any) -> List[Notice]:
        """Converts the creation request to a list of database model documents

        Args:
            database: the database where the notice templates are stored
            kwargs: the extra kwargs passed to each created record

        Returns:
             the list of notices that come from the CustomNoticeCreate
        """
        # imported here to avoid a circular import, as the auth service imports this one
        from services.auth.users.dtos import User

        kwargs = dict(
            severity=self.severity,
            expires_at=self.expires_at,
            starts_at=self.starts_at,
            **kwargs,
        )
        context = CustomNoticeContext(
            title=self.message,
            body=self.message,
        )
        if self.target_user_emails:
            users = await database.find(
                User, filter={"email": {"$in": self.target_user_emails}}
            )
            template = await database.get(NoticeTemplate, NoticeType.CUSTOM.id)
            return [
                Notice.from_template(
                    template=template, context=context, user_id=user.id, **kwargs
                )
                for user in users
            ]

        template = await database.get(NoticeTemplate, NoticeType.CUSTOM_BROADCAST.id)
        return [Notice.from_template(template=template, context=context, **kwargs)]
