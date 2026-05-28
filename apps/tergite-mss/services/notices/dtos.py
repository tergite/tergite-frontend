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
#
from contextlib import suppress
from datetime import datetime
from enum import Enum
from typing import List, Optional, Any

from beanie import Document, PydanticObjectId
from pydantic import Field, BaseModel, field_serializer, field_validator
from pymongo import IndexModel

from utils.date_time import get_current_timestamp, datetime_to_zulu, get_utc_now

NOTICE_DB_COLLECTION = "notices"


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


class NoticeCreate(BaseModel):
    message: str
    severity: NoticeSeverity
    expires_at: datetime = Field(default_factory=get_utc_now)
    starts_at: datetime = Field(default_factory=get_utc_now)
    target_user_emails: Optional[List[str]] = None

    @field_serializer("expires_at", "starts_at", when_used="json")
    def serialize_expires_at(self, value: datetime):
        """Convert datetime value to string when working with JSON"""
        return datetime_to_zulu(value)


class Notice(NoticeCreate, Document):
    created_by: PydanticObjectId
    target_user_ids: Optional[List[PydanticObjectId]] = None
    dismissed_by: List[PydanticObjectId] = Field(default_factory=list)
    severity_number: int = Field(validation_alias="severity")
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    class Settings:
        name = NOTICE_DB_COLLECTION
        indexes = [
            IndexModel("dismissed_by", sparse=True),
            IndexModel("expires_at", expireAfterSeconds=0),
            IndexModel(("starts_at", "expires_at")),
        ]

    @field_validator("severity_number", mode="before")
    @classmethod
    def validate_severity_number(cls, value: Any):
        if isinstance(value, (str, NoticeSeverity)):
            with suppress(ValueError):
                return NoticeSeverity(value).to_int()
        return value
