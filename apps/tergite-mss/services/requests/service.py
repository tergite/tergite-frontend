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

import motor.motor_asyncio
from beanie import init_beanie

from typing import Any, Dict, List, Optional, Sequence, Tuple

from beanie import PydanticObjectId, UpdateResponse

import settings
from services import notices
from utils.config import UserRole
from utils.exc import ConflictError, ForbiddenError, NotFoundError, TooManyRequestsError

from .dtos import (
    Request,
    RequestStatus,
    RequestType,
    RequestPostBody,
    RequestUpdate, RequestTarget,
)
from services.auth.users.dtos import User
from services.auth.projects.dtos import Project

_DECIDED_STATUSES = (RequestStatus.APPROVED, RequestStatus.REJECTED)
ALL_REQ_TYPES = tuple(RequestType)


async def on_startup(db: motor.motor_asyncio.AsyncIOMotorDatabase):
    """Runs init operations when the application is starting up"""
    await init_beanie(
        database=db,
        document_models=[
            Request,
        ],
    )


# CRUD
async def create(
    request_body: RequestPostBody,
    requester: User,
) -> Request:
    """Creates a new user request given the request body, requester_id and request type

    Args:
        request_body: the POST body of the request
        requester: the user making the request

    Returns:
        the created Request object
    """
    target_user_ids = await _get_target_user_ids(request_body)
    record = Request.from_post_body(request_body, requester=requester, target_user_ids=target_user_ids)
    await record.create()
    # NOTE: We explicitly notify here instead of in a beanie hook because:
    #   - hooks would have hidden the logic to a reader/maintainer in future
    #   - we have been using beanie and motor/pymongo interchangeably
    #     We don't want some functions to miss out on the hooks
    await notices.create_system_notice(
        user_ids=target_user_ids,
        notice_type=record.notice_type.id,
        ref_id=record.ref_id,
        ref_type=record.metadata.resource,
        context=record.notice_context,
    )
    return record

async def get_one(pk: PydanticObjectId, current_user_id: PydanticObjectId) -> Request:
    """Gets a single request if the given user is allowed to see it

    Args:
        pk: the id of the request
        current_user_id: the identifier of the current user

    Returns:
        the Request object

    Raises:
        NotFoundError if the request is not found
    """
    record = await Request.find_one({
        "_id": pk,
        "$or": [{"target_user_ids": current_user_id},
                {"requester_id": current_user_id}],
    })
    if record is None:
        raise NotFoundError(f"{pk} not found")
    return record


async def get_many(current_user_id: PydanticObjectId,filter_obj: Optional[Dict[str, Any]] = None,
                   request_types: Tuple[RequestType] = ALL_REQ_TYPES,
    skip: int = 0,
    limit: Optional[int] = None,) -> List[Request]:
    """Gets multiple requests that match the given filter and request types and can be viewed by current user

    Requesters and target users of a given request can view the it

    Args:
        current_user_id: the identifier of the current user
        filter_obj: the PyMongo-like filter object e.g. `{"approver_id": "some-guys-id"}`.
        request_types: the types of request to return. default = ALL_REQ_TYPES
        skip: the number of matched records to skip
        limit: the maximum number of records to return.
                If None, all possible records are returned.

    Returns:
        the list of request objects
    """
    _filter = {} if filter_obj is None else {**filter_obj}
    _filter.update({"type": {"$in": request_types}, "$or": [{"target_user_ids": current_user_id},
                {"requester_id": current_user_id}]})
    return await Request.find(filter_obj, skip=skip, limit=limit).to_list()

async def update():
    """Updates the matched requests"""

async def delete():
    """Deletes the matched requests"""


# async def get_many_qpu_time_requests(
#     filter_obj: Optional[Dict[str, Any]] = None,
#     skip: int = 0,
#     limit: Optional[int] = None,
# ) -> List[Request]:
#     """Retrieves the user requests that match the given filter
#
#     Args:
#         filter_obj: the PyMongo-like filter object e.g. `{"approver_id": "some-guys-id"}`.
#         skip: the number of matched records to skip
#         limit: the maximum number of records to return.
#                 If None, all possible records are returned.
#
#     Returns:
#         the list of user request objects
#     """
#     _filter = {} if filter_obj is None else {**filter_obj}
#     _filter.update({"type": RequestType.PROJECT_QPU_SECONDS})
#     return await get_many(_filter, skip=skip, limit=limit)


# async def create_qpu_time_request(
#     request_body: ProjectQpuSecondsPostBody, requester: User
# ) -> Request:
#     """Creates a new user request given the request body, requester_id and request type
#
#     Args:
#         request_body: the POST body of the request
#         requester: the user making the request
#
#     Returns:
#         the created Request object
#     """
#     record = await create(
#         request_body=request_body,
#         requester=requester,
#         request_type=RequestType.PROJECT_QPU_SECONDS,
#         # QPU time is a system-level allocation: project admins request it, system
#         # admins grant it. Unchanged from before this flow gained a scope field.
#         approver_scope=ApproverScope.SYSTEM_ADMIN,
#         project_id=request_body.project_id,
#     )
#     await notifications.notify(
#         await _get_target_user_ids(record),
#         NotificationType.QPU_SECONDS_REQUESTED,
#         context={
#             "project_name": request_body.project_name,
#             "requester_name": requester.username,
#             "reason": request_body.reason,
#             "seconds": f"{request_body.seconds:.0f}",
#         },
#         action=NotificationAction(kind="user-request", request_id=str(record.id)),
#     )
#     return record


async def get_many_as_requester(
    requester_id: str,
    status: Optional[RequestStatus] = None,
    types: Sequence[RequestType] = (),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Request]:
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
        await Request.find(filter_obj, skip=skip, limit=limit)
        .sort("-created_at")
        .to_list()
    )


async def get_many_as_approver(
    approver: User,
    status: Optional[RequestStatus] = None,
    types: Sequence[RequestType] = (),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Request]:
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
        await Request.find(filter_obj, skip=skip, limit=limit)
        .sort("-created_at")
        .to_list()
    )


async def is_eligible_approver(approver: User, request: Request) -> bool:
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
    payload: RequestUpdate,
    admin_user: User,
) -> Request:
    """Approves or rejects the user request of the given id

    Approval side effects are applied before the request is marked decided, so that a
    failure leaves a retryable pending request rather than an approved request with
    nothing done. All side effects are idempotent.

    Args:
        _id: the unique identifier of the user request
        payload: the PUT body of the request
        admin_user: the user reacting to the request

    Returns:
        the updated Request object

    Raises:
        NotFoundError: {_id} not found
        ForbiddenError: you are not entitled to react to this request
        ConflictError: request has already been {status}
    """
    request = await Request.find_one({"_id": _id})
    if request is None:
        raise NotFoundError(f"{_id} not found")

    if not await is_eligible_approver(admin_user, request):
        raise ForbiddenError("you are not entitled to react to this request")

    if payload.status is not None and request.status in _DECIDED_STATUSES:
        raise ConflictError(f"request has already been {request.status.value}")

    if payload.status == RequestStatus.APPROVED:
        await _apply_approval(request)

    defaults = RequestUpdate()
    if payload.status is not None:
        defaults.approver_name = admin_user.username
        defaults.approver_id = str(admin_user.id)

    result: Request = await Request.find_one({"_id": _id}).update(
        {"$set": {**payload.model_dump(), **defaults.model_dump()}},
        response_type=UpdateResponse.NEW_DOCUMENT,
    )
    if result is None:
        raise NotFoundError(f"{_id} not found")

    if payload.status in _DECIDED_STATUSES:
        await notifications.mark_ref_handled(str(_id))
        await _notify_requester(result, admin_user)

    return result


async def _apply_approval(request: Request):
    """Applies the side effect of approving the given request

    Args:
        request: the request being approved

    Raises:
        NotFoundError: project {id} not found
    """
    if request.type == RequestType.PROJECT_QPU_SECONDS:
        project = await ProjectDatabase.increment_qpu_seconds(
            request.request.project_id, request.request.seconds
        )
        if project is None:
            raise NotFoundError(f"project {request.request.project_id} not found")

    elif request.type == RequestType.PROJECT_ACCESS:
        requester = await User.find_one({"_id": PydanticObjectId(request.requester_id)})
        if requester is None:
            raise NotFoundError(f"user {request.requester_id} not found")

        project = await ProjectDatabase.add_member(
            request.project_id, request.requester_id, requester.email
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
    pending = await Request.find(
        {"requester_id": requester_id, "status": RequestStatus.PENDING}
    ).count()
    if pending >= maximum:
        raise TooManyRequestsError(
            f"too many pending requests; at most {maximum} allowed"
        )


async def _get_target_user_ids(
    request: RequestPostBody
) -> List[PydanticObjectId]:
    """Gets the IDs of users to whom this request is directed

    Args:
        request: the request post body

    Returns:
        the IDs of the target users

    Raises:
        NotFoundError: project {id} not found
    """
    if request.target == RequestTarget.PROJECT:
        project = await Project.get(request.resource_id)
        if project is None:
            raise NotFoundError(f"project {request.resource_id} not found")
        return [PydanticObjectId(project.admin_id)]

    elif request.target == RequestTarget.SYSTEM:
        superusers = await User.find({"roles": UserRole.ADMIN}).to_list()
        return [user.id for user in superusers]

    return []


async def _notify_requester(request: Request, approver: User):
    """Tells the requester what was decided about their request

    Args:
        request: the decided request
        approver: the user who decided it
    """
    is_approved = request.status == RequestStatus.APPROVED
    decision_types = {
        RequestType.PROJECT_ACCESS: (
            NotificationType.PROJECT_ACCESS_APPROVED
            if is_approved
            else NotificationType.PROJECT_ACCESS_REJECTED
        ),
        RequestType.PROJECT_QPU_SECONDS: (
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
    status: Optional[RequestStatus],
    types: Sequence[RequestType],
):
    """Adds the status and type filters to the given mongodb filter object"""
    if status is not None:
        filter_obj["status"] = status
    if len(types) > 0:
        filter_obj["type"] = {"$in": list(types)}
