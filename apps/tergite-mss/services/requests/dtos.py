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
from functools import cached_property
from typing import Any, Callable, List, Literal, Optional, Self, Tuple, Type

from beanie import Document, PydanticObjectId
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    computed_field,
    field_serializer,
    field_validator,
)
from pydantic.main import IncEx
from pymongo import IndexModel

from services.auth import User
from services.auth.projects.dtos import ProjectCreate
from services.notices import NoticeType
from services.notices.dtos import ProjectRequestContext, RefType
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


class RequestMetadata(BaseModel):
    """The metadata for a given request"""

    resource: RefType


class CreateProjectMetadata(RequestMetadata, ProjectCreate):
    """The metadata for a request to create a new project"""


class CloseProjectMetadata(RequestMetadata):
    """Metadata for requesting a project close"""


class TransferProjectMetadata(RequestMetadata):
    """Metadata for requesting a project transfer"""

    admin_email: str


class ProjectQpuSecondsMetadata(RequestMetadata):
    """Metadata for requesting a project qpu seconds"""

    # FIXME: Not sure if project_name is necessary
    project_name: Optional[str] = None


class ProjectAccessMetadata(RequestMetadata):
    """Metadata for requesting access to a project"""

    # FIXME: Not sure if project_name is necessary
    project_name: Optional[str] = None


class RequestPostBody(BaseModel):
    """The POST body sent for a request"""

    resource_id: PydanticObjectId
    type: RequestType
    reason: str
    metadata: Optional[RequestMetadata] = None

    __type_target_map__ = {
        RequestType.CREATE_PROJECT: RequestTarget.SYSTEM,
        RequestType.CLOSE_PROJECT: RequestTarget.SYSTEM,
        RequestType.TRANSFER_PROJECT: RequestTarget.SYSTEM,
        RequestType.PROJECT_QPU_SECONDS: RequestTarget.SYSTEM,
        RequestType.PROJECT_ACCESS: RequestTarget.PROJECT,
    }

    __type_metadata_cls_map__: dict[RequestType, Type[RequestMetadata]] = {
        RequestType.CREATE_PROJECT: ProjectCreate,
        RequestType.CLOSE_PROJECT: CloseProjectMetadata,
        RequestType.TRANSFER_PROJECT: TransferProjectMetadata,
        RequestType.PROJECT_QPU_SECONDS: ProjectQpuSecondsMetadata,
        RequestType.PROJECT_ACCESS: ProjectAccessMetadata,
    }

    @computed_field
    @cached_property
    def target(self) -> RequestTarget:
        """The target for this request"""
        return self.__type_target_map__[self.type]

    @field_validator("metadata", mode="before")
    @classmethod
    def has_right_metadata_type(
        cls, value: Any, info: ValidationInfo
    ) -> RequestMetadata:
        req_type = RequestType(info.data["type"])
        try:
            metadata_cls = cls.__type_metadata_cls_map__[req_type]
        except KeyError:
            raise ValueError(f"request type {req_type} not supported")

        return metadata_cls.model_validate(value)


class Request(RequestPostBody, Document):
    """The schema for all user requests that have to be approved/rejected by an admin"""

    requester_id: PydanticObjectId
    requester_name: Optional[str] = None
    target_user_ids: List[PydanticObjectId]
    status: RequestStatus = RequestStatus.PENDING
    approver_id: Optional[PydanticObjectId] = None
    approver_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    __type_status_notice_map__: dict[Tuple[RequestType, RequestStatus], NoticeType] = {
        # project creation
        (
            RequestType.CREATE_PROJECT,
            RequestStatus.PENDING,
        ): NoticeType.PROJECT_CREATE_REQUESTED,
        (
            RequestType.CREATE_PROJECT,
            RequestStatus.REJECTED,
        ): NoticeType.PROJECT_CREATE_REJECTED,
        (
            RequestType.CREATE_PROJECT,
            RequestStatus.APPROVED,
        ): NoticeType.PROJECT_CREATE_APPROVED,
        # closing projects
        (
            RequestType.CLOSE_PROJECT,
            RequestStatus.PENDING,
        ): NoticeType.PROJECT_CLOSE_REQUESTED,
        (
            RequestType.CLOSE_PROJECT,
            RequestStatus.REJECTED,
        ): NoticeType.PROJECT_CLOSE_REJECTED,
        (
            RequestType.CLOSE_PROJECT,
            RequestStatus.APPROVED,
        ): NoticeType.PROJECT_CLOSE_APPROVED,
        # project transfer
        (
            RequestType.TRANSFER_PROJECT,
            RequestStatus.PENDING,
        ): NoticeType.PROJECT_TRANSFER_REQUESTED,
        (
            RequestType.TRANSFER_PROJECT,
            RequestStatus.REJECTED,
        ): NoticeType.PROJECT_TRANSFER_REJECTED,
        (
            RequestType.TRANSFER_PROJECT,
            RequestStatus.APPROVED,
        ): NoticeType.PROJECT_TRANSFER_APPROVED,
        # QPU seconds requests
        (
            RequestType.PROJECT_QPU_SECONDS,
            RequestStatus.PENDING,
        ): NoticeType.QPU_SECONDS_REQUESTED,
        (
            RequestType.PROJECT_QPU_SECONDS,
            RequestStatus.REJECTED,
        ): NoticeType.QPU_SECONDS_DENIED,
        (
            RequestType.PROJECT_QPU_SECONDS,
            RequestStatus.APPROVED,
        ): NoticeType.QPU_SECONDS_GRANTED,
        # project access
        (
            RequestType.PROJECT_ACCESS,
            RequestStatus.PENDING,
        ): NoticeType.PROJECT_ACCESS_REQUESTED,
        (
            RequestType.PROJECT_ACCESS,
            RequestStatus.REJECTED,
        ): NoticeType.PROJECT_ACCESS_REJECTED,
        (
            RequestType.PROJECT_ACCESS,
            RequestStatus.APPROVED,
        ): NoticeType.PROJECT_ACCESS_APPROVED,
    }

    class Settings:
        name = REQUEST_DB_COLLECTION
        indexes = [
            IndexModel(["type"]),
            IndexModel([("resource_id", 1), ("status", 1)], sparse=True),
            IndexModel([("requester_id", 1), ("created_at", -1)]),
        ]

    @field_serializer(
        "id", "requester_id", "approver_id", "resource_id", when_used="json"
    )
    def serialize_ids(self, _id: PydanticObjectId):
        """Convert id to string when working with JSON"""
        return str(_id)

    @property
    def notice_type(self) -> NoticeType:
        """The notice type for this request given current status"""
        return self.__type_status_notice_map__[(self.type, self.status)]

    @property
    def notice_context(self) -> ProjectRequestContext:
        """The context for the notice that is to be sent out for the given request"""
        project_name = ""
        project_ext_id = ""
        approver_name = ""
        seconds = ""
        admin_email = ""
        metadata = self.metadata

        if isinstance(metadata, CreateProjectMetadata):
            project_name = metadata.name
            project_ext_id = metadata.ext_id

        elif isinstance(metadata, CloseProjectMetadata):
            pass

        elif isinstance(metadata, TransferProjectMetadata):
            admin_email = metadata.admin_email

        elif isinstance(metadata, ProjectQpuSecondsMetadata):
            project_name = metadata.project_name or ""

        elif isinstance(metadata, ProjectAccessMetadata):
            project_name = metadata.project_name or ""

        return ProjectRequestContext(
            requester_name=self.requester_name,
            project_name=project_name,
            project_ext_id=project_ext_id,
            reason=self.reason,
            approver_name=approver_name,
            seconds=seconds,
            admin_email=admin_email,
        )

    @classmethod
    def from_post_body(
        cls,
        body: RequestPostBody,
        requester: User,
        target_user_ids: List[PydanticObjectId],
    ) -> Self:
        """Creates a request object given the request post body and requester

        Args:
            body: The request post body
            requester: The request post requester
            target_user_ids: The IDs for the target users

        Returns:
            the request object
        """
        return cls(
            **body.model_dump(),
            requester_id=requester.id,
            requester_name=requester.username,
            target_user_ids=target_user_ids,
        )


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
