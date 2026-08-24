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
"""Data Transfer Objects for bulk QPU-second grants"""
import enum
from typing import List, Optional

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, field_serializer, model_validator
from pymongo import IndexModel

from utils.date_time import get_current_timestamp

QPU_SECONDS_GRANT_DB_COLLECTION = "qpu_seconds_grants"


class GrantTarget(str, enum.Enum):
    """Who a bulk grant applies to"""

    EMAILS = "emails"
    ALL_PERSONAL_PROJECTS = "all-personal-projects"


class SkippedTarget(BaseModel):
    """A target the grant could not be applied to, and why"""

    email: str
    why: str


class QpuSecondsGrantCreate(BaseModel):
    """The POST body for granting QPU seconds to many personal projects at once"""

    seconds: float = Field(gt=0)
    target: GrantTarget
    target_emails: Optional[List[str]] = None
    reason: str

    @model_validator(mode="after")
    def emails_required_for_email_target(self) -> "QpuSecondsGrantCreate":
        """An email-targeted grant without emails would silently affect nobody"""
        if self.target == GrantTarget.EMAILS and not self.target_emails:
            raise ValueError("target_emails is required when target is 'emails'")
        return self


class QpuSecondsGrant(QpuSecondsGrantCreate, Document):
    """The record of one bulk grant operation.

    One document per operation rather than per recipient: `$inc` is not idempotent, and
    the unique index on idempotency_key is what makes a replayed request a no-op.
    """

    granted_by: PydanticObjectId
    idempotency_key: str
    granted_project_ids: List[str] = Field(default_factory=list)
    skipped: List[SkippedTarget] = Field(default_factory=list)
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)

    class Settings:
        name = QPU_SECONDS_GRANT_DB_COLLECTION
        indexes = [
            IndexModel("idempotency_key", unique=True),
            IndexModel([("created_at", -1)]),
        ]

    @field_serializer("id", when_used="json")
    def serialize_id(self, _id: PydanticObjectId):
        """Convert id to string when working with JSON"""
        return str(_id)

    @field_serializer("granted_by", when_used="json")
    def serialize_granted_by(self, value: PydanticObjectId):
        """Convert granted_by to string when working with JSON"""
        return str(value)


class QpuSecondsGrantReport(BaseModel):
    """The response to a grant: what was applied and what was not.

    Partial application is normal, so the skipped list is the useful part.
    """

    seconds: float
    granted: int
    skipped: List[SkippedTarget] = Field(default_factory=list)
