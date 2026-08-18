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
from typing import Any, Dict, List, Optional, Sequence, Union

from beanie import PydanticObjectId, UpdateResponse

import settings
from services import notifications
from services.notifications import NotificationAction, NotificationType
from utils import rate_limit
from utils.exc import ConflictError, ForbiddenError, NotFoundError, TooManyRequestsError

from utils.config import UserRole

from ..projects.database import ProjectDatabase
from ..projects.dtos import Project
from ..users.dtos import User
from .dtos import (
    ApproverScope,
    ProjectAccessPostBody,
    QpuTimeExtensionPostBody,
    UserRequest,
    UserRequestStatus,
    UserRequestType,
    UserRequestUpdate,
)

_DECIDED_STATUSES = (UserRequestStatus.APPROVED, UserRequestStatus.REJECTED)

__all__ = [
    "ApproverScope",
    "ProjectAccessPostBody",
    "QpuTimeExtensionPostBody",
    "UserRequest",
    "UserRequestStatus",
    "UserRequestType",
    "UserRequestUpdate",
    "create",
    "create_project_access_request",
    "create_qpu_time_request",
    "get_many",
    "get_many_as_approver",
    "get_many_as_requester",
    "get_many_qpu_time_requests",
    "is_eligible_approver",
    "update",
]


async def get_many_qpu_time_requests(
    filter_obj: Optional[Dict[str, Any]] = None,
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[UserRequest]:
    """Retrieves the user requests that match the given filter

    Args:
        filter_obj: the PyMongo-like filter object e.g. `{"approver_id": "some-guys-id"}`.
        skip: the number of matched records to skip
        limit: the maximum number of records to return.
                If None, all possible records are returned.

    Returns:
        the list of user request objects
    """
    _filter = {} if filter_obj is None else {**filter_obj}
    _filter.update({"type": UserRequestType.PROJECT_QPU_SECONDS})
    return await get_many(_filter, skip=skip, limit=limit)


async def create_qpu_time_request(
    request_body: QpuTimeExtensionPostBody, requester: User
) -> UserRequest:
    """Creates a new user request given the request body, requester_id and request type

    Args:
        request_body: the POST body of the request
        requester: the user making the request

    Returns:
        the created UserRequest object
    """
    record = await create(
        request_body=request_body,
        requester=requester,
        request_type=UserRequestType.PROJECT_QPU_SECONDS,
        # QPU time is a system-level allocation: project admins request it, system
        # admins grant it. Unchanged from before this flow gained a scope field.
        approver_scope=ApproverScope.SYSTEM_ADMIN,
        project_id=request_body.project_id,
    )
    await notifications.notify(
        await _approver_ids(record),
        NotificationType.QPU_SECONDS_REQUESTED,
        context={
            "project_name": request_body.project_name,
            "requester_name": requester.username,
            "reason": request_body.reason,
            "seconds": f"{request_body.seconds:.0f}",
        },
        action=NotificationAction(kind="user-request", request_id=str(record.id)),
    )
    return record


async def get_many(
    filter_obj: Dict[str, Any], skip: int = 0, limit: Optional[int] = None
) -> List[UserRequest]:
    """Retrieves the user requests that match the given filter

    Args:
        filter_obj: the PyMongo-like filter object e.g. `{"type": "project-qpu-seconds"}`.
        skip: the number of matched records to skip
        limit: the maximum number of records to return.
                If None, all possible records are returned.

    Returns:
        the list of user request objects
    """
    return await UserRequest.find(filter_obj, skip=skip, limit=limit).to_list()


async def create(
    request_body: Union[
        QpuTimeExtensionPostBody, ProjectAccessPostBody, Dict[str, Any]
    ],
    requester: User,
    request_type: UserRequestType,
    approver_scope: ApproverScope = ApproverScope.SYSTEM_ADMIN,
    project_id: Optional[str] = None,
) -> UserRequest:
    """Creates a new user request given the request body, requester_id and request type

    Args:
        request_body: the POST body of the request
        requester: the user making the request
        request_type: the type of request being made
        approver_scope: who may react to the request; default = SYSTEM_ADMIN
        project_id: the project the request concerns, if any

    Returns:
        the created UserRequest object
    """
    record = UserRequest(
        request=request_body,
        requester_id=str(requester.id),
        type=request_type,
        requester_name=requester.username,
        approver_scope=approver_scope,
        project_id=project_id,
    )
    await record.create()
    return record


async def create_project_access_request(
    body: ProjectAccessPostBody, requester: User
) -> UserRequest:
    """Creates a request for access to an existing shared project.

    Args:
        body: the POST body naming the project by its ext_id
        requester: the user asking for access

    Returns:
        the created UserRequest object

    Raises:
        TooManyRequestsError: too many pending requests, or too many failed lookups
        NotFoundError: no project with ID '{ext_id}'
        ConflictError: already a member of, or already has a pending request for, the project
    """
    requester_id = str(requester.id)
    await _assert_pending_quota(requester_id)
    # checked before the lookup so tripping the limit reveals nothing about the outcome
    rate_limit.check(
        f"project-lookup:{requester_id}",
        limit=settings.CONFIG.projects.max_failed_lookups_per_hour,
    )

    # $ne rather than False so projects predating the field still match
    project = await Project.find_one(
        {"ext_id": body.project_ext_id, "is_personal": {"$ne": True}}
    )
    if project is None:
        rate_limit.increment(f"project-lookup:{requester_id}")
        raise NotFoundError(f"no project with ID '{body.project_ext_id}'")

    if requester_id in (project.user_ids or []) or requester.email in (
        project.user_emails or []
    ):
        raise ConflictError(f"you are already a member of '{body.project_ext_id}'")

    duplicate = await UserRequest.find_one(
        {
            "requester_id": requester_id,
            "type": UserRequestType.PROJECT_ACCESS,
            "project_id": str(project.id),
            "status": UserRequestStatus.PENDING,
        }
    )
    if duplicate is not None:
        raise ConflictError(f"a request for '{body.project_ext_id}' is already pending")

    body.project_name = project.name
    record = await create(
        request_body=body,
        requester=requester,
        request_type=UserRequestType.PROJECT_ACCESS,
        approver_scope=ApproverScope.PROJECT_ADMIN,
        project_id=str(project.id),
    )
    await notifications.notify(
        await _approver_ids(record, project=project),
        NotificationType.PROJECT_ACCESS_REQUESTED,
        context={
            "project_name": project.name,
            "project_ext_id": project.ext_id,
            "requester_name": requester.username,
            "reason": body.reason,
        },
        action=NotificationAction(kind="user-request", request_id=str(record.id)),
    )
    return record


async def get_many_as_requester(
    requester_id: str,
    status: Optional[UserRequestStatus] = None,
    types: Sequence[UserRequestType] = (),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[UserRequest]:
    """Retrieves the requests made by the given user

    Args:
        requester_id: the ID of the user who made the requests
        status: the status to filter by; default = None i.e. any
        types: the request types to filter by; default = () i.e. any
        skip: the number of matched records to skip
        limit: the maximum number of records to return

    Returns:
        the list of user request objects, newest first
    """
    filter_obj: Dict[str, Any] = {"requester_id": requester_id}
    _apply_common_filters(filter_obj, status=status, types=types)
    return (
        await UserRequest.find(filter_obj, skip=skip, limit=limit)
        .sort("-created_at")
        .to_list()
    )


async def get_many_as_approver(
    approver: User,
    status: Optional[UserRequestStatus] = None,
    types: Sequence[UserRequestType] = (),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[UserRequest]:
    """Retrieves the requests the given user is entitled to react to

    A superuser sees every request. Anyone else sees only project-admin-scoped requests
    for the projects they administer, excluding their own.

    Args:
        approver: the user who would react to the requests
        status: the status to filter by; default = None i.e. any
        types: the request types to filter by; default = () i.e. any
        skip: the number of matched records to skip
        limit: the maximum number of records to return

    Returns:
        the list of user request objects, newest first
    """
    filter_obj: Dict[str, Any] = {}
    _apply_common_filters(filter_obj, status=status, types=types)

    if not approver.is_superuser:
        administered = await Project.find(
            {"admin_id": str(approver.id), "is_personal": {"$ne": True}}
        ).to_list()
        filter_obj.update(
            {
                "approver_scope": ApproverScope.PROJECT_ADMIN,
                "project_id": {"$in": [str(item.id) for item in administered]},
                "requester_id": {"$ne": str(approver.id)},
            }
        )

    return (
        await UserRequest.find(filter_obj, skip=skip, limit=limit)
        .sort("-created_at")
        .to_list()
    )


async def is_eligible_approver(approver: User, request: UserRequest) -> bool:
    """Whether the given user may react to the given request

    Args:
        approver: the user who wants to react
        request: the request to react to

    Returns:
        True if the user may approve or reject the request
    """
    if approver.is_superuser:
        return True

    if request.approver_scope != ApproverScope.PROJECT_ADMIN:
        return False

    # defence in depth: nothing currently reaches this, since a project admin is already
    # a member and so cannot file an access request for their own project
    if str(approver.id) == request.requester_id:
        return False

    if request.project_id is None:
        return False

    project = await Project.find_one({"_id": PydanticObjectId(request.project_id)})
    return project is not None and project.admin_id == str(approver.id)


async def update(
    _id: PydanticObjectId,
    payload: UserRequestUpdate,
    admin_user: User,
) -> UserRequest:
    """Approves or rejects the user request of the given id

    Approval side effects are applied before the request is marked decided, so that a
    failure leaves a retryable pending request rather than an approved request with
    nothing done. All side effects are idempotent.

    Args:
        _id: the unique identifier of the user request
        payload: the PUT body of the request
        admin_user: the user reacting to the request

    Returns:
        the updated UserRequest object

    Raises:
        NotFoundError: {_id} not found
        ForbiddenError: you are not entitled to react to this request
        ConflictError: request has already been {status}
    """
    request = await UserRequest.find_one({"_id": _id})
    if request is None:
        raise NotFoundError(f"{_id} not found")

    if not await is_eligible_approver(admin_user, request):
        raise ForbiddenError("you are not entitled to react to this request")

    if payload.status is not None and request.status in _DECIDED_STATUSES:
        raise ConflictError(f"request has already been {request.status.value}")

    if payload.status == UserRequestStatus.APPROVED:
        await _apply_approval(request)

    defaults = UserRequestUpdate()
    if payload.status is not None:
        defaults.approver_name = admin_user.username
        defaults.approver_id = str(admin_user.id)

    result: UserRequest = await UserRequest.find_one({"_id": _id}).update(
        {"$set": {**payload.model_dump(), **defaults.model_dump()}},
        response_type=UpdateResponse.NEW_DOCUMENT,
    )
    if result is None:
        raise NotFoundError(f"{_id} not found")

    if payload.status in _DECIDED_STATUSES:
        await _notify_requester(result, admin_user)

    return result


async def _apply_approval(request: UserRequest):
    """Applies the side effect of approving the given request

    Args:
        request: the request being approved

    Raises:
        NotFoundError: project {id} not found
    """
    if request.type == UserRequestType.PROJECT_QPU_SECONDS:
        project = await ProjectDatabase.increment_qpu_seconds(
            request.request.project_id, request.request.seconds
        )
        if project is None:
            raise NotFoundError(f"project {request.request.project_id} not found")

    elif request.type == UserRequestType.PROJECT_ACCESS:
        requester = await User.find_one({"_id": PydanticObjectId(request.requester_id)})
        if requester is None:
            raise NotFoundError(f"user {request.requester_id} not found")

        project = await Project.find_one(
            {"_id": PydanticObjectId(request.project_id)}
        ).update(
            {
                "$addToSet": {
                    "user_ids": request.requester_id,
                    "user_emails": requester.email,
                }
            },
            response_type=UpdateResponse.NEW_DOCUMENT,
        )
        if project is None:
            raise NotFoundError(f"project {request.project_id} not found")


async def _assert_pending_quota(requester_id: str):
    """Raises if the user already has the maximum number of pending requests

    Args:
        requester_id: the ID of the user making a new request

    Raises:
        TooManyRequestsError: too many pending requests; at most {max} allowed
    """
    maximum = settings.CONFIG.projects.max_pending_requests_per_user
    pending = await UserRequest.find(
        {"requester_id": requester_id, "status": UserRequestStatus.PENDING}
    ).count()
    if pending >= maximum:
        raise TooManyRequestsError(
            f"too many pending requests; at most {maximum} allowed"
        )


async def _approver_ids(
    request: UserRequest, project: Optional[Project] = None
) -> List[PydanticObjectId]:
    """The users entitled to react to the given request

    Args:
        request: the request awaiting a decision
        project: the request's project, when the caller already has it

    Returns:
        the recipient IDs, excluding the requester
    """
    if request.approver_scope == ApproverScope.PROJECT_ADMIN:
        if project is None and request.project_id is not None:
            project = await Project.find_one(
                {"_id": PydanticObjectId(request.project_id)}
            )
        admin_id = getattr(project, "admin_id", None)
        ids = [PydanticObjectId(admin_id)] if admin_id else []
    else:
        superusers = await User.find({"roles": UserRole.ADMIN}).to_list()
        ids = [user.id for user in superusers]

    return [item for item in ids if str(item) != request.requester_id]


async def _notify_requester(request: UserRequest, approver: User):
    """Tells the requester what was decided about their request

    Args:
        request: the decided request
        approver: the user who decided it
    """
    is_approved = request.status == UserRequestStatus.APPROVED
    decision_types = {
        UserRequestType.PROJECT_ACCESS: (
            NotificationType.PROJECT_ACCESS_APPROVED
            if is_approved
            else NotificationType.PROJECT_ACCESS_REJECTED
        ),
        UserRequestType.PROJECT_QPU_SECONDS: (
            NotificationType.QPU_SECONDS_GRANTED
            if is_approved
            else NotificationType.QPU_SECONDS_DENIED
        ),
    }
    type_ = decision_types.get(request.type)
    if type_ is None:
        return

    body = request.request
    await notifications.notify(
        [PydanticObjectId(request.requester_id)],
        type_,
        context={
            "project_name": getattr(body, "project_name", None) or "your project",
            "approver_name": approver.username,
            "reason": request.rejection_reason or "",
            "seconds": f"{getattr(body, 'seconds', 0):.0f}",
        },
    )


def _apply_common_filters(
    filter_obj: Dict[str, Any],
    status: Optional[UserRequestStatus],
    types: Sequence[UserRequestType],
):
    """Adds the status and type filters to the given mongodb filter object"""
    if status is not None:
        filter_obj["status"] = status
    if len(types) > 0:
        filter_obj["type"] = {"$in": list(types)}
