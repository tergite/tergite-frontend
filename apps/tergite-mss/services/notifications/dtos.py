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
"""Data Transfer Objects for the notifications service"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pymongo import IndexModel

from utils.date_time import get_current_timestamp

NOTIFICATION_DB_COLLECTION = "notifications"
NOTIFICATION_PREFS_DB_COLLECTION = "notification_preferences"


class NotificationSeverity(str, Enum):
    """How much attention a notification deserves.

    Deliberately its own enum rather than reusing NoticeSeverity: the two channels are
    separate by design, and importing notices here makes notifications depend on the auth
    service transitively.
    """

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationType(str, Enum):
    """The kinds of notification the system emits.

    Each member must have a producer; add one only alongside the code that emits it.
    """

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


class NotificationAction(BaseModel):
    """What the recipient can do about a notification, rendered as buttons in the UI"""

    kind: Literal["user-request"]
    request_id: str


class EmailStatus(str, Enum):
    """Delivery state of the email copy of a notification.

    The notification row doubles as the email outbox, so this is what the sweeper reads.
    """

    NOT_APPLICABLE = "not-applicable"
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class ChannelPrefs(BaseModel):
    """Per-type delivery preferences for one user"""

    in_app: bool = True
    email: bool = True


class NotificationRead(BaseModel):
    """A notification as seen by its recipient"""

    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    type: NotificationType
    title: str
    body: str
    severity: NotificationSeverity
    action: Optional[NotificationAction] = None
    context: Dict[str, Any] = {}
    read_at: Optional[str] = None
    created_at: Optional[str] = None

    @field_serializer("id", when_used="json")
    def serialize_id(self, _id: PydanticObjectId):
        """Convert id to string when working with JSON"""
        return str(_id)


class NotificationUpdate(BaseModel):
    """The PUT body for marking a notification read or unread"""

    is_read: bool


class Notification(Document):
    """A per-recipient, event-driven message.

    Distinct from a Notice, which is an admin-authored broadcast with its own expiry and
    shared dismissal state.
    """

    user_id: PydanticObjectId
    type: NotificationType
    title: str
    body: str
    severity: NotificationSeverity = NotificationSeverity.INFO
    action: Optional[NotificationAction] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    read_at: Optional[str] = None
    email_status: EmailStatus = EmailStatus.NOT_APPLICABLE
    email_attempts: int = 0
    # kept bounded by a TTL index rather than manual pruning
    expires_at: Optional[datetime] = None
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    class Settings:
        name = NOTIFICATION_DB_COLLECTION
        indexes = [
            IndexModel([("user_id", 1), ("created_at", -1)]),
            IndexModel([("user_id", 1), ("read_at", 1)]),
            IndexModel([("email_status", 1), ("updated_at", 1)], sparse=True),
            IndexModel("expires_at", expireAfterSeconds=0),
        ]

    @field_serializer("id", when_used="json")
    def serialize_id(self, _id: PydanticObjectId):
        """Convert id to string when working with JSON"""
        return str(_id)


class NotificationPreferences(Document):
    """One user's opt-outs, owned by this service rather than by the auth service"""

    user_id: PydanticObjectId
    prefs: Dict[NotificationType, ChannelPrefs] = Field(default_factory=dict)
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    class Settings:
        name = NOTIFICATION_PREFS_DB_COLLECTION
        indexes = [IndexModel("user_id", unique=True)]
