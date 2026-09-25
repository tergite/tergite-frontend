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
import dataclasses
from datetime import datetime
from enum import Enum, nonmember
from typing import Annotated, Any, Dict, List, Optional, Self, Type, TypeAlias

from beanie import Document, PydanticObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_core.core_schema import ValidationInfo
from pymongo import IndexModel

from utils.date_time import datetime_to_zulu, get_current_timestamp, get_utc_now
from utils.models import create_partial_model

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


class NoticeSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    def to_int(self) -> int:
        """Gets the number corresponding to this notice severity"""
        if self == NoticeSeverity.INFO:
            return 3
        if self == NoticeSeverity.WARNING:
            return 2
        if self == NoticeSeverity.CRITICAL:
            return 1
        raise ValueError(f"Invalid notice severity: {self}")


class BaseNoticeContext(BaseModel):
    """The base class for the context passed to the notice template."""

    model_config = ConfigDict(extra="allow")


class ProjectRequestContext(BaseNoticeContext):
    """The context passed to the notice template when anything is requested about a project."""

    requester_name: str = ""
    project_name: str = ""
    reason: str = ""
    approver_name: str = ""
    seconds: float | str = ""
    admin_email: str = ""


class CustomNoticeContext(BaseNoticeContext):
    """The context for custom notices."""

    title: str = ""
    body: str = ""


@dataclasses.dataclass(frozen=True, eq=True)
class NoticeTypeInfo:
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

    __str_member_map__ = nonmember({})

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Gets the NoticeTypeEnum from a string.

        Raises:
            KeyError: if the string is not a valid notice type.
        """
        if not cls.__str_member_map__:
            cls.__str_member_map__ = {v.id: v for v in cls}
        return cls.__str_member_map__[value]

    @classmethod
    def validate_str(cls, value: str) -> str:
        """Validates a string as a member of this enum"""
        try:
            current = cls.from_str(value)
            return current.id
        except KeyError:
            raise ValueError(f"invalid notice type string value {value}")

    def __str__(self):
        return self.id


NoticeTypeId: TypeAlias = Annotated[str, BeforeValidator(NoticeType.validate_str)]
"""A kind of NoticeTypes"""


class Notice(Document):
    """A message"""

    model_config = ConfigDict(extra="ignore")

    type: NoticeTypeId
    title: str
    body: str
    user_id: Optional[PydanticObjectId] = None
    # 'created_by' is specific to custom notices
    created_by: Optional[PydanticObjectId] = None
    severity: NoticeSeverity = NoticeSeverity.INFO
    ref_type: Optional[RefType] = None
    ref_id: Optional[PydanticObjectId] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    email_status: EmailStatus = EmailStatus.NOT_APPLICABLE
    email_attempts: int = 0
    # read_at and dismissed_by must be atomically set for non-broadcast messages
    read_at: Optional[str] = None
    dismissed_by: List[PydanticObjectId] = Field(default_factory=list)
    starts_at: Optional[datetime] = None
    # kept bounded by a TTL index rather than manual pruning
    expires_at: Optional[datetime] = None
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    class Settings:
        name = NOTICE_DB_COLLECTION
        indexes = [
            IndexModel("dismissed_by", sparse=True),
            IndexModel([("user_id", 1), ("created_at", -1)]),
            IndexModel([("user_id", 1), ("read_at", 1)]),
            IndexModel([("email_status", 1), ("updated_at", 1)], sparse=True),
            IndexModel("expires_at", expireAfterSeconds=0),
            IndexModel(("starts_at", "expires_at")),
            IndexModel(("ref_type", "ref_id"), sparse=True),
        ]
        validate_on_save = True

    @computed_field
    @property
    def severity_number(self) -> int:
        """The notice severity number"""
        return self.severity.to_int()

    @field_serializer("id", when_used="json")
    def serialize_object_fields(self, value: Any):
        """Convert object fields to string when working with JSON"""
        return str(value)

    @field_serializer(
        "expires_at", "starts_at", "created_at", "updated_at", when_used="json"
    )
    def serialize_date_fields(self, value: Optional[datetime]) -> Optional[str]:
        """Convert datetime value to string when working with JSON"""
        try:
            return datetime_to_zulu(value)
        except AttributeError:
            return value

    @field_validator("title", "body", mode="after")
    @classmethod
    def compute_template_fields(cls, value: str, info: ValidationInfo) -> str:
        """Computes the templates of the title and the body using the context"""
        ctx = info.context
        if isinstance(ctx, BaseNoticeContext):
            return value.format_map(ctx.model_dump())
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
        context: BaseNoticeContext,
        **kwargs,
    ) -> Self:
        """Constructs a notice from a template

        Args:
            template: The notice template
            context: The notice context useful for formating the template
            kwargs: Additional arguments passed to the notice constructor

        Returns:
            The notice object
        """
        data = {**template.model_dump(), **kwargs}
        return cls.model_validate(data, context=context)


class NoticePreferences(Document):
    """One user's opt-outs, owned by this service rather than by the auth service"""

    user_id: PydanticObjectId
    email_prefs: Dict[NoticeTypeId, bool] = Field(default_factory=dict)
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    class Settings:
        name = NOTICE_PREFS_DB_COLLECTION
        indexes = [IndexModel("user_id", unique=True)]


class NoticeTemplate(Document):
    """The templates for each notice type persisted and updated in the database"""

    type: NoticeTypeId
    title: str
    body: str
    severity: NoticeSeverity
    context_cls: Type[BaseNoticeContext] = BaseNoticeContext

    class Settings:
        name = TEMPLATE_DB_COLLECTION
        indexes = [
            IndexModel("type", unique=True),
        ]

    @field_serializer("id", when_used="json")
    def serialize_id(self, value: Any):
        """Convert id fields to string when working with JSON"""
        return str(value)

    @field_serializer("context_cls")
    def serialize_object_fields(self, value: Any):
        """Convert object fields to string always"""
        return str(value)

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
            context_cls=value.context_cls,
        )


class CustomNoticeCreate(BaseModel):
    """The schema for creating custom notices"""

    message: str
    severity: NoticeSeverity
    expires_at: datetime = Field(default_factory=get_utc_now)
    starts_at: datetime = Field(default_factory=get_utc_now)
    target_user_emails: Optional[List[str]] = None

    async def to_documents(
        self, db: AsyncIOMotorDatabase, **kwargs: Any
    ) -> List[Notice]:
        """Converts the creation request to a list of database model documents

        Args:
            db: the database instance where data is saved
            kwargs: the extra kwargs passed to each created record

        Returns:
             the list of notices that come from the CustomNoticeCreate
        """
        from services.auth.users.dtos import USER_DB_COLLECTION

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
        users_col = db[USER_DB_COLLECTION]
        templates_col = db[TEMPLATE_DB_COLLECTION]

        if self.target_user_emails:
            cursor = users_col.find(
                {"email": {"$in": self.target_user_emails}}, {"_id": 1}
            )
            template = await templates_col.find_one({"type": NoticeType.CUSTOM.id})

            return [
                Notice.from_template(
                    template=template, context=context, user_id=v["_id"], **kwargs
                )
                for v in await cursor.to_list()
            ]

        template = await templates_col.find_one(
            {"type": NoticeType.CUSTOM_BROADCAST.id}
        )
        return [Notice.from_template(template=template, context=context, **kwargs)]


NoticeTemplatePartial = create_partial_model("NoticeTemplatePartial", NoticeTemplate)
"""The partial notice template to be used when updating the database"""

CustomNoticeCreatePartial = create_partial_model(
    "CustomNoticeCreatePartial", CustomNoticeCreate
)
"""The partial custom notice to be used when updating the database"""
