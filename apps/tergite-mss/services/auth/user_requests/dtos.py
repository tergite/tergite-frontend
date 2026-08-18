# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import enum
from typing import Any, Callable, Dict, Literal, Optional, Union

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, field_serializer, field_validator, validator
from pydantic.main import IncEx
from pydantic_core.core_schema import ValidationInfo
from pymongo import IndexModel

from utils.date_time import get_current_timestamp

USER_REQUEST_DB_COLLECTION = "auth_user_requests"


class UserRequestStatus(str, enum.Enum):
    """The state of the user request"""

    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


class UserRequestType(str, enum.Enum):
    """The types of user requests"""

    # reserved for RFC 0002; declared but not yet wired up
    CREATE_PROJECT = "create-project"
    CLOSE_PROJECT = "close-project"
    TRANSFER_PROJECT = "transfer-project"
    PROJECT_QPU_SECONDS = "project-qpu-seconds"
    PROJECT_ACCESS = "project-access"


class ApproverScope(str, enum.Enum):
    """Who is entitled to react to a request"""

    SYSTEM_ADMIN = "system-admin"
    PROJECT_ADMIN = "project-admin"


class QpuTimeExtensionPostBody(BaseModel):
    """The POST body sent when requesting for more QPU time"""

    project_id: str
    seconds: float
    reason: str
    project_name: Optional[str] = None


class ProjectAccessPostBody(BaseModel):
    """The POST body sent when requesting access to a shared project"""

    type: Literal[UserRequestType.PROJECT_ACCESS] = UserRequestType.PROJECT_ACCESS
    project_ext_id: str
    reason: str
    project_name: Optional[str] = None


class UserRequest(Document):
    """The schema for all user requests that have to be approved/rejected by an admin"""

    type: UserRequestType
    requester_id: str
    requester_name: Optional[str] = None
    status: UserRequestStatus = UserRequestStatus.PENDING
    approver_id: Optional[str] = None
    approver_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    # defaults to SYSTEM_ADMIN so requests predating this field keep their old behaviour
    approver_scope: ApproverScope = ApproverScope.SYSTEM_ADMIN
    # promoted out of `request` so the project-admin inbox is a single indexed query
    project_id: Optional[str] = None
    request: Union[
        QpuTimeExtensionPostBody, ProjectAccessPostBody, Dict[str, Any]
    ] = Field(default_factory=dict)
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    class Settings:
        name = USER_REQUEST_DB_COLLECTION
        indexes = [
            IndexModel([("project_id", 1), ("status", 1)], sparse=True),
            IndexModel([("requester_id", 1), ("created_at", -1)]),
        ]

    @field_serializer("id", when_used="json")
    def serialize_id(self, _id: PydanticObjectId):
        """Convert id to string when working with JSON"""
        return str(_id)

    @classmethod
    @field_validator("type")
    def type_depends_on_request(cls, v: UserRequestType, info: ValidationInfo):
        try:
            if v == UserRequestType.PROJECT_QPU_SECONDS and not isinstance(
                info.data["request"], QpuTimeExtensionPostBody
            ):
                raise ValueError(f"must be {UserRequestType.PROJECT_QPU_SECONDS}")
        except (TypeError, KeyError):
            pass
        return v

    @classmethod
    @field_validator("request")
    def request_depends_on_type(
        cls, v: Union[QpuTimeExtensionPostBody, Dict[str, Any]], info: ValidationInfo
    ):
        try:
            if info.data[
                "type"
            ] == UserRequestType.PROJECT_QPU_SECONDS and not isinstance(
                v, QpuTimeExtensionPostBody
            ):
                raise ValueError(
                    f"must be of type {QpuTimeExtensionPostBody.__class__.__name__}"
                )
        except (TypeError, KeyError):
            pass
        return v


class UserRequestUpdate(UserRequest):
    """The schema for updating user requests"""

    type: Optional[UserRequestType] = None
    requester_id: Optional[str] = None
    requester_name: Optional[str] = None
    status: Optional[UserRequestStatus] = None
    approver_id: Optional[str] = None
    approver_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    approver_scope: Optional[ApproverScope] = None
    project_id: Optional[str] = None
    request: Optional[
        Union[QpuTimeExtensionPostBody, ProjectAccessPostBody, Dict[str, Any]]
    ] = None
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        exclude_unset: bool = True,
        exclude_defaults: bool = False,
        exclude_none: bool = True,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        fallback: Callable[[Any], Any] | None = None,
        serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            fallback=fallback,
            serialize_as_any=serialize_as_any,
        )
