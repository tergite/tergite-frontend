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
from typing import Any, Dict, List, Optional, Self

from beanie import Document, PydanticObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, computed_field, field_serializer, model_validator
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


class NoticeType(str, Enum):
    """The kinds of notices."""

    PROJECT_ACCESS_REQUESTED = "project-access-requested"
    PROJECT_ACCESS_APPROVED = "project-access-approved"
    PROJECT_ACCESS_REJECTED = "project-access-rejected"
    QPU_SECONDS_REQUESTED = "qpu-seconds-requested"
    QPU_SECONDS_GRANTED = "qpu-seconds-granted"
    QPU_SECONDS_DENIED = "qpu-seconds-denied"
    QPU_SECONDS_LOW = "qpu-seconds-low"
    QPU_SECONDS_DEPLETED = "qpu-seconds-depleted"
    PROJECT_MEMBERSHIP_GRANTED = "project-membership-granted"
    PROJECT_MEMBERSHIP_REVOKED = "project-membership-revoked"
    PROJECT_ADMIN_ASSIGNED = "project-admin-assigned"
    CUSTOM = "custom"
    CUSTOM_BROADCAST = "custom-broadcast"


class NoticeTemplate(BaseModel):
    """The templates for each notice type"""

    title: str
    body: str
    severity: NoticeSeverity


class Notice(Document):
    """A message"""

    type: "NoticeType"
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
        ]
        validate_on_save = True

    @computed_field
    @property
    def severity_number(self) -> int:
        """The notice severity number"""
        return self.severity.to_int()

    @field_serializer("id", when_used="json")
    def serialize_id(self, _id: PydanticObjectId):
        """Convert id to string when working with JSON"""
        return str(_id)

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
    @classmethod
    def validate_record(cls, data: Any) -> Self:
        """Validates the notice record

        For example:
            - 'created_by' cannot be None if 'type' of notice is custom
            - 'user_id' cannot be None if 'type' is not custom-broadcast
            - 'user_id' must be None if 'type' is custom-broadcast
            - if 'read_at' is set then the 'dismissed_by' field must include the 'user_id' if type is not custom-broadcast
            - 'read_at' must be None if 'type' is custom-broadcast

        """
        if not isinstance(data, dict):
            return data

        notice_type = data.get("type")
        user_id = data.get("user_id")
        read_at = data.get("read_at")
        dismissed_by = data.get("dismissed_by")

        if data.get("created_by") is None and notice_type == NoticeType.CUSTOM:
            raise ValueError("Custom notice cannot be created by no one")
        if notice_type == NoticeType.CUSTOM_BROADCAST:
            if user_id:
                raise ValueError(
                    "Custom broadcast notices should not have target users"
                )
            if read_at:
                raise ValueError("Custom broadcast notices can not have read_at set")
        else:
            if user_id is None:
                raise ValueError("Non-broadcast notices should have target users")
            if read_at and (not dismissed_by or user_id not in dismissed_by):
                raise ValueError(
                    "Non-broadcast notices when read must also append user_id to dismissed_by"
                )

        return data


class NoticePreferences(Document):
    """One user's opt-outs, owned by this service rather than by the auth service"""

    user_id: PydanticObjectId
    email_prefs: Dict[NoticeType, bool] = Field(default_factory=dict)
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    class Settings:
        name = NOTICE_PREFS_DB_COLLECTION
        indexes = [IndexModel("user_id", unique=True)]


class NoticeTemplateInDb(NoticeTemplate, Document):
    """The templates for each notice type persisted and updated in the database"""

    type: NoticeType

    class Settings:
        name = TEMPLATE_DB_COLLECTION
        indexes = [
            IndexModel("type", unique=True),
        ]


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

        if self.target_user_emails:
            cursor = db[USER_DB_COLLECTION].find(
                {"email": {"$in": self.target_user_emails}}, {"_id": 1}
            )
            return [
                Notice(
                    user_id=v["_id"],
                    title=self.message,
                    body=self.message,
                    severity=self.severity,
                    expires_at=self.expires_at,
                    starts_at=self.starts_at,
                    type=NoticeType.CUSTOM,
                    **kwargs,
                )
                for v in await cursor.to_list()
            ]

        return [
            Notice(
                title=self.message,
                body=self.message,
                severity=self.severity,
                expires_at=self.expires_at,
                starts_at=self.starts_at,
                type=NoticeType.CUSTOM_BROADCAST,
                **kwargs,
            )
        ]


NoticePartial = create_partial_model("NoticePartial", Notice)
"""The partial notice to be used when updating the database"""

NoticeTemplatePartial = create_partial_model(
    "NoticeTemplatePartial", NoticeTemplateInDb
)
"""The partial notice template to be used when updating the database"""

CustomNoticeCreatePartial = create_partial_model(
    "CustomNoticeCreatePartial", CustomNoticeCreate
)
"""The partial custom notice to be used when updating the database"""
