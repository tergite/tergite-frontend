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
import asyncio
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import motor.motor_asyncio
from beanie import PydanticObjectId
from beanie.odm.operators.find.comparison import In
from pydantic import BaseModel, Field

from services import notices
from services.auth.projects.dtos import Project
from services.auth.users.dtos import User
from utils.config import UserRole
from utils.exc import ForbiddenError, NotFoundError
from utils.mongodb import extract_sort_config, init_strict_beanie

from . import actions
from .dtos import (
    Request,
    RequestPostBody,
    RequestStatus,
    RequestTarget,
    RequestType,
    RequestUpdate,
)

_DECIDED_STATUSES = (RequestStatus.APPROVED, RequestStatus.REJECTED)
ALL_REQ_TYPES = tuple(RequestType)
ALL_REQ_STATUSES = tuple(RequestStatus)


async def on_startup(db: motor.motor_asyncio.AsyncIOMotorDatabase):
    """Runs init operations when the application is starting up"""
    await init_strict_beanie(
        database=db,
        document_models=[
            Request,
        ],
    )


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

    Raises:
        ForbiddenError: operation not permitted on resource {id}
        NotFoundError: project {id} not found
    """
    if not await _has_resource_access(request_body, user=requester):
        raise ForbiddenError(
            f"operation not permitted on resource {request_body.resource_id}"
        )

    target_user_ids = await _get_target_user_ids(request_body)
    record = Request.from_post_body(
        request_body, requester=requester, target_user_ids=target_user_ids
    )
    await record.create()
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
    record = await Request.find_one(
        {
            "_id": pk,
            "$or": [
                {"target_user_ids": current_user_id},
                {"requester_id": current_user_id},
            ],
        }
    )
    if record is None:
        raise NotFoundError(f"{pk} not found")
    return record


async def get_many(
    filter_obj: Dict[str, Any],
    current_user_id: PydanticObjectId,
    request_types: Tuple[RequestType, ...] = ALL_REQ_TYPES,
    sort: tuple[str, ...] = ("-created_at",),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Request]:
    """Gets multiple requests that match the given filter and request types and can be viewed by current user

    Requesters and target users of a given request can view it

    Args:
        filter_obj: the PyMongo-like filter object e.g. `{"approver_id": "some-guys-id"}`.
        current_user_id: the identifier of the current user
        request_types: the types of request to return. default = ALL_REQ_TYPES
        sort: the sort order of the returned results
        skip: the number of matched records to skip
        limit: the maximum number of records to return.
                If None, all possible records are returned.

    Returns:
        the list of request objects
    """
    _filter = {
        **filter_obj,
        "type": {"$in": request_types},
        "$or": [
            {"target_user_ids": current_user_id},
            {"requester_id": current_user_id},
        ],
    }
    return await Request.find(
        _filter,
        skip=skip,
        limit=limit,
        sort=extract_sort_config(sort),
    ).to_list()


async def update(
    filter_obj: Dict[str, Any],
    payload: RequestUpdate,
    current_user: User,
    sort: tuple[str, ...] = ("-created_at",),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Request]:
    """Updates the matched requests.

    Note: only approvers can update a request that has been made.
    Requesters can delete and create another.
    The reasoning is updating it would require we send a new notice
    and the approver might get confused about which is which.

    Note: We don't change the status of finalized requests
    for the same reason of the potential of misalignment. Better
    to make a new request.

    Approval side effects are applied before the requests are marked decided, so that a
    failure leaves a retryable pending request rather than an approved request with
    nothing done.

    Args:
        filter_obj: the filters to match
        payload: the update payload for the requests
        current_user: the logged-in user
        sort: the sort order of the returned results
        skip: the number of matched records to skip
        limit: the maximum number of records to match.
                If None, all possible records are matched.

    Returns:
        Returns all updated requests

    Raises:
        NotFoundError: no match found
        NotFoundError: project {id} not found
        NotFoundError: no users of emails {emails}
        ConflictError: a project named '{name}' already exists
    """
    _filter = {} if filter_obj is None else {**filter_obj}
    # only requests that are pending can be updated
    # only requests that a user is a target can be updated
    _filter.update(
        {"target_user_ids": current_user.id, "status": RequestStatus.PENDING}
    )
    sort_args = extract_sort_config(sort)

    # found first, as approving needs them, and update_many can neither skip nor limit
    matches = await Request.find(
        _filter, skip=skip, limit=limit, sort=sort_args
    ).to_list()
    if len(matches) == 0:
        raise NotFoundError("no match found")

    if payload.status == RequestStatus.APPROVED:
        await actions.do_many_actions(matches, approver=current_user)

    # updated_at is never set by the client, so exclude_unset would drop its default
    update_dict = payload.model_dump(exclude_unset=True)
    update_dict.update(
        {
            "approver_id": current_user.id,
            "approver_name": current_user.username,
            "updated_at": payload.updated_at,
        }
    )
    ids = [item.id for item in matches]
    await Request.find(In(Request.id, ids)).update({"$set": update_dict})
    result = [item.model_copy(update=update_dict) for item in matches]

    if payload.status in _DECIDED_STATUSES:
        ref_type_ids_map = defaultdict(list)
        for item in result:
            ref_type_ids_map[item.metadata.resource].append(item.id)

        # clear the notice for all possible approvers
        await notices.clear_notices_by_reference(ref_type_ids_map)

        # update requester
        await asyncio.gather(
            *(
                notices.create_system_notice(
                    user_ids=(item.requester_id,),
                    notice_type=item.notice_type.id,
                    ref_id=item.id,
                    ref_type=item.metadata.resource,
                    context=item.notice_context,
                )
                for item in result
            )
        )
    return result


async def _get_target_user_ids(request: RequestPostBody) -> List[PydanticObjectId]:
    """Gets the IDs of users to whom this request is directed

    Args:
        request: the request post body

    Returns:
        the IDs of the target users

    Raises:
        NotFoundError: project {id} not found
    """
    if request.target == RequestTarget.PROJECT:
        # personal projects answer as missing ones do, so they cannot be probed
        project = await Project.find_one(
            Project.id == request.resource_id,
            Project.is_personal != True,
            projection_model=_TrimmedProject,
        )
        if project is None:
            raise NotFoundError(f"project {request.resource_id} not found")

        return [project.admin_id]

    elif request.target == RequestTarget.SYSTEM:
        superusers = await User.find({"roles": UserRole.ADMIN}).to_list()
        return [user.id for user in superusers]

    return []


async def _has_resource_access(request: RequestPostBody, user: User) -> bool:
    """Checks if the user has access to the resource they are requesting on

    Args:
        request: the request post body
        user: the user to check

    Returns:
        True if the user has access to the resource
    """
    if request.type == RequestType.CREATE_PROJECT:
        return user is not None

    elif request.type in (RequestType.CLOSE_PROJECT, RequestType.TRANSFER_PROJECT):
        project = await Project.find_one(
            Project.id == request.resource_id,
            Project.admin_id == user.id,
            projection_model=_TrimmedProject,
        )
        return project is not None
    elif request.type == RequestType.PROJECT_QPU_SECONDS:
        project = await Project.find_one(
            Project.id == request.resource_id,
            Project.user_ids == user.id,
            projection_model=_TrimmedProject,
        )
        return project is not None
    elif request.type == RequestType.PROJECT_ACCESS:
        return user is not None

    return False


class _TrimmedProject(BaseModel):
    """A project with only its _id and admin_id"""

    id: PydanticObjectId = Field(alias="_id")
    admin_id: PydanticObjectId
