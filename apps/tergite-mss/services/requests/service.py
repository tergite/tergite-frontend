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
from typing import List, Optional, Sequence, Tuple

from libs.storage import Database
from services import notices
from services.auth.projects.dtos import Project
from services.auth.users.dtos import User
from utils.config import UserRole
from utils.exc import ForbiddenError, NotFoundError

from . import actions
from .dtos import (
    Request,
    RequestPostBody,
    RequestRole,
    RequestStatus,
    RequestTarget,
    RequestType,
    RequestUpdate,
)

_DECIDED_STATUSES = (RequestStatus.APPROVED, RequestStatus.REJECTED)
ALL_REQ_TYPES = tuple(RequestType)
ALL_REQ_STATUSES = tuple(RequestStatus)


async def create(
    database: Database,
    request_body: RequestPostBody,
    requester: User,
) -> Request:
    """Creates a new user request given the request body, requester_id and request type

    Args:
        request_body: the POST body of the request
        requester: the user making the request

    Returns:
        the created Request object

    Raises:
        ForbiddenError: operation not permitted on resource {id}
        NotFoundError: project {id} not found
    """
    if not await _has_resource_access(database, request_body, user=requester):
        raise ForbiddenError(
            f"operation not permitted on resource {request_body.resource_id}"
        )

    target_user_ids = await _get_target_user_ids(database, request_body)
    record = Request.from_post_body(
        request_body, requester=requester, target_user_ids=target_user_ids
    )
    await database.insert(Request, record)
    # NOTE: We explicitly notify here instead of in a beanie hook because:
    #   - hooks would have hidden the logic to a reader/maintainer in future
    await notices.create_system_notice(
        user_ids=target_user_ids,
        notice_type=record.notice_type.id,
        ref_id=record.id,
        ref_type=record.metadata.resource,
        context=record.notice_context,
    )
    return record


async def get_one(database: Database, pk: str, current_user_id: str) -> Request:
    """Gets a single request if the given user is allowed to see it

    Args:
        pk: the id of the request
        current_user_id: the identifier of the current user

    Returns:
        the Request object

    Raises:
        NotFoundError if the request is not found
    """
    current_user_id = str(current_user_id)
    record = await database.find_one(
        Request,
        filter={
            "id": str(pk),
            "$or": [
                {"target_user_ids": current_user_id},
                {"requester_id": current_user_id},
            ],
        },
    )
    if record is None:
        raise NotFoundError(f"{pk} not found")
    return record


async def get_many(
    database: Database,
    current_user_id: str,
    role: RequestRole,
    statuses: Tuple[RequestStatus, ...] = ALL_REQ_STATUSES,
    request_types: Tuple[RequestType, ...] = ALL_REQ_TYPES,
    sort: Sequence[str] = ("-created_at",),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Request]:
    """Gets the requests the current user made, or those awaiting their decision

    Args:
        database: the database where the requests are stored
        current_user_id: the identifier of the current user
        role: "requester" for the user's own requests, "approver" for those targeting them
        statuses: the statuses of request to return. default = ALL_REQ_STATUSES
        request_types: the types of request to return. default = ALL_REQ_TYPES
        sort: the fields to sort by; a leading '-' sorts descending
        skip: the number of matched requests to skip
        limit: the most requests to return; None returns all

    Returns:
        the list of request objects
    """
    user_field = "target_user_ids" if role == "approver" else "requester_id"
    request_filter = {
        user_field: str(current_user_id),
        "status": {"$in": list(statuses)},
        "type": {"$in": list(request_types)},
    }
    return await database.find(
        Request, filter=request_filter, sort=sort, skip=skip, limit=limit
    )


async def update(
    database: Database, pk: str, payload: RequestUpdate, current_user: User
) -> Request:
    """Decides the pending request of the given id that awaits the current user

    Note: only approvers can update a request that has been made.
    Requesters can delete and create another.
    The reasoning is updating it would require we send a new notice
    and the approver might get confused about which is which.

    Note: We don't change the status of finalized requests
    for the same reason of the potential of misalignment. Better
    to make a new request.

    Approval side effects are applied before the request is marked decided, so that a
    failure leaves a retryable pending request rather than an approved request with
    nothing done.

    Args:
        database: the database where the requests are stored
        pk: the id of the request
        payload: the update payload for the request
        current_user: the logged-in user

    Returns:
        the updated request

    Raises:
        NotFoundError: no match found
        NotFoundError: project {id} not found
        NotFoundError: no users of emails {emails}
        ConflictError: a project named '{name}' already exists
    """
    # only pending requests that target the user can be updated
    record = await database.find_one(
        Request,
        filter={
            "id": str(pk),
            "target_user_ids": str(current_user.id),
            "status": RequestStatus.PENDING,
        },
    )
    if record is None:
        raise NotFoundError("no match found")

    if payload.status == RequestStatus.APPROVED:
        await actions.do_many_actions(database, [record], approver=current_user)

    # updated_at is never set by the client, so exclude_unset would drop its default
    changes = payload.model_dump(exclude_unset=True)
    changes.update(
        {
            "approver_id": str(current_user.id),
            "approver_name": current_user.username,
            "updated_at": payload.updated_at,
        }
    )
    await database.update_one(Request, {"id": record.id}, {"$set": changes})
    updated_record = record.model_copy(update=changes)

    if payload.status in _DECIDED_STATUSES:
        resource = updated_record.metadata.resource
        # clear the notice for all possible approvers
        await notices.clear_notices_by_reference({resource: [updated_record.id]})
        await notices.create_system_notice(
            user_ids=(updated_record.requester_id,),
            notice_type=updated_record.notice_type.id,
            ref_id=updated_record.id,
            ref_type=resource,
            context=updated_record.notice_context,
        )
    return updated_record


async def _get_target_user_ids(
    database: Database, request: RequestPostBody
) -> List[str]:
    """Gets the IDs of users to whom this request is directed

    Args:
        database: the database where the projects are stored
        request: the request post body

    Returns:
        the IDs of the target users

    Raises:
        NotFoundError: project {id} not found
    """
    if request.target == RequestTarget.PROJECT:
        # personal projects answer as missing ones do, so they cannot be probed
        project = await database.find_one(
            Project, {"id": request.resource_id, "is_personal": {"$ne": True}}
        )
        if project is None:
            raise NotFoundError(f"project {request.resource_id} not found")

        return [project.admin_id]

    elif request.target == RequestTarget.SYSTEM:
        superusers = await User.find({"roles": UserRole.ADMIN}).to_list()
        return [str(user.id) for user in superusers]

    return []


async def _has_resource_access(
    database: Database, request: RequestPostBody, user: User
) -> bool:
    """Checks if the user has access to the resource they are requesting on

    Args:
        database: the database where the projects are stored
        request: the request post body
        user: the user to check

    Returns:
        True if the user has access to the resource
    """
    if request.type == RequestType.CREATE_PROJECT:
        return user is not None

    elif request.type in (RequestType.CLOSE_PROJECT, RequestType.TRANSFER_PROJECT):
        project = await database.find_one(
            Project,
            {"id": request.resource_id, "admin_id": str(user.id)},
        )
        return project is not None
    elif request.type == RequestType.PROJECT_QPU_SECONDS:
        project = await database.find_one(
            Project,
            {"id": request.resource_id, "user_ids": str(user.id)},
        )
        return project is not None
    elif request.type == RequestType.PROJECT_ACCESS:
        return user is not None

    return False
