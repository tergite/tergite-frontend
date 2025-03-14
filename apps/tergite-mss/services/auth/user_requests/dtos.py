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
from typing import Any, Dict, Optional, Union

from beanie import Document
from pydantic import BaseModel, Field, validator

from utils.date_time import get_current_timestamp

USER_REQUEST_DB_COLLECTION = "auth_user_requests"


class UserRequestStatus(str, enum.Enum):
    """The state of the user request"""

    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


class UserRequestType(str, enum.Enum):
    """The types of user requests"""

    CREATE_PROJECT = "create-project"
    CLOSE_PROJECT = "close-project"
    TRANSFER_PROJECT = "transfer-project"
    PROJECT_QPU_SECONDS = "project-qpu-seconds"


class QpuTimeExtensionPostBody(BaseModel):
    """The POST body sent when requesting for more QPU time"""

    project_id: str
    seconds: float
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
    request: Union[QpuTimeExtensionPostBody, Dict[str, Any]] = Field(
        default_factory=dict
    )
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    class Settings:
        name = USER_REQUEST_DB_COLLECTION

    @validator("type")
    def type_depends_on_request(cls, v, values, **kwargs):
        try:
            if v == UserRequestType.PROJECT_QPU_SECONDS and not isinstance(
                values["request"], QpuTimeExtensionPostBody
            ):
                raise ValueError(f"must be {UserRequestType.PROJECT_QPU_SECONDS}")
        except (TypeError, KeyError):
            pass
        return v

    @validator("request")
    def request_depends_on_type(cls, v, values, **kwargs):
        try:
            if values["type"] == UserRequestType.PROJECT_QPU_SECONDS and not isinstance(
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
    request: Optional[Union[QpuTimeExtensionPostBody, Dict[str, Any]]] = None
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    def dict(self, *args, **kwargs):
        exclude_none = kwargs.get("exclude_none", True)
        exclude_unset = kwargs.get("exclude_unset", True)
        return super().dict(
            *args, **kwargs, exclude_none=exclude_none, exclude_unset=exclude_unset
        )
