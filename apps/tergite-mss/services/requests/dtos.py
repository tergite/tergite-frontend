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
from typing import Any, Dict, List, Literal, Optional, Type

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializeAsAny,
    ValidationInfo,
    computed_field,
    field_validator,
)

from libs.storage import Id, Schema, StorageSpec, generate_id
from services.auth.projects.dtos import ProjectCreate
from services.notices.dtos import RefType
from utils.date_time import get_current_timestamp

# FIXME:
#   We probably need to associate every request with one target user and one requester
#   The actions they do can be controlled at the instance when the actions are done
#   i.e. if they still have permissions at that time, the action succeeds otherwise
#   it is rejected

# FIXME: Question - how do we unify the requests api. Some requests are for admins only
#   while other requests are any user.
#   - Maybe we can have 'system requests' and 'user requests'
#   - system requests go to the system and are approved of by a system admin
#   - user requests are requests to a given user
#   - Come to think of it, we probably need project requests also
#   - Maybe we can have one struct --- Request --- with a type field with Enum('system','project','user')
#   - And all are CRUD through `/requests`
#   - And basing on type, the appropriate people are notified
#   - And in the dashboard, only one page is available of requests: just filterable by type

REQUEST_DB_COLLECTION = "requests"


class RequestTarget(str, enum.Enum):
    """The targets for each given request"""

    SYSTEM = "system"
    PROJECT = "project"
    # we probably don't need users as targets of requests
    # USER = "user"


type RequestRole = Literal["requester", "approver"]
"""Whose requests to list: the ones the user made, or those awaiting their decision"""


class RequestStatus(str, enum.Enum):
    """The state of the user request"""

    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


class RequestType(str, enum.Enum):
    """The types of user requests"""

    CREATE_PROJECT = "create-project"
    CLOSE_PROJECT = "close-project"
    TRANSFER_PROJECT = "transfer-project"
    PROJECT_QPU_SECONDS = "project-qpu-seconds"
    PROJECT_ACCESS = "project-access"


_REQUEST_TARGETS: Dict[RequestType, RequestTarget] = {
    RequestType.CREATE_PROJECT: RequestTarget.SYSTEM,
    RequestType.CLOSE_PROJECT: RequestTarget.SYSTEM,
    RequestType.TRANSFER_PROJECT: RequestTarget.SYSTEM,
    RequestType.PROJECT_QPU_SECONDS: RequestTarget.SYSTEM,
    RequestType.PROJECT_ACCESS: RequestTarget.PROJECT,
}


class RequestMetadata(BaseModel):
    """The metadata for a given request"""

    resource: RefType = RefType.PROJECT


class CreateProjectMetadata(RequestMetadata, ProjectCreate):
    """The metadata for a request to create a new project"""


class CloseProjectMetadata(RequestMetadata):
    """Metadata for requesting a project close"""


class TransferProjectMetadata(RequestMetadata):
    """Metadata for requesting a project transfer"""

    admin_email: str


class ProjectQpuSecondsMetadata(RequestMetadata):
    """Metadata for requesting a project qpu seconds"""

    seconds: float = Field(gt=0)


class ProjectAccessMetadata(RequestMetadata):
    """Metadata for requesting access to a project"""


_METADATA_CLASSES: Dict[RequestType, Type[RequestMetadata]] = {
    RequestType.CREATE_PROJECT: CreateProjectMetadata,
    RequestType.CLOSE_PROJECT: CloseProjectMetadata,
    RequestType.TRANSFER_PROJECT: TransferProjectMetadata,
    RequestType.PROJECT_QPU_SECONDS: ProjectQpuSecondsMetadata,
    RequestType.PROJECT_ACCESS: ProjectAccessMetadata,
}


class RequestPostBody(BaseModel):
    """The POST body sent for a request"""

    resource_id: Id
    type: RequestType
    reason: str
    # SerializeAsAny, or the fields of the subclass are dropped when saving
    metadata: Optional[SerializeAsAny[RequestMetadata]] = Field(
        default=None, validate_default=True
    )

    @computed_field
    @property
    def target(self) -> RequestTarget:
        """The target for this request"""
        return _REQUEST_TARGETS[self.type]

    @field_validator("metadata", mode="before")
    @classmethod
    def has_right_metadata_type(
        cls, value: Any, info: ValidationInfo
    ) -> RequestMetadata:
        req_type = RequestType(info.data["type"])
        try:
            metadata_cls = _METADATA_CLASSES[req_type]
        except KeyError:
            raise ValueError(f"request type {req_type} not supported")

        if isinstance(value, BaseModel):
            value = value.model_dump()
        return metadata_cls.model_validate({} if value is None else value)


class Request(Schema, RequestPostBody):
    """The schema for all user requests that have to be approved/rejected by an admin"""

    __storage__ = StorageSpec(
        table=REQUEST_DB_COLLECTION,
        indexed_lists=("target_user_ids",),
        indexes=("type", ("resource_id", "status"), ("requester_id", "-created_at")),
    )

    id: Id = Field(default_factory=generate_id)
    requester_id: Id
    requester_name: Optional[str] = None
    target_user_ids: List[Id]
    status: RequestStatus = RequestStatus.PENDING
    approver_id: Optional[Id] = None
    approver_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)


class RequestUpdate(BaseModel):
    """The schema for updating requests.

    Note that only a few things can be updated on a request
    because once a request is sent, correcting it by updating
    would cause misalignment between involved parties
    """

    model_config = ConfigDict(extra="forbid")

    status: Optional[RequestStatus] = None
    rejection_reason: Optional[str] = None
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)
