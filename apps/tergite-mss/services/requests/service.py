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
from typing import List, Sequence, Tuple

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from libs.storage import And, Database, Eq, Filter, In, Or, Page, Set, Sort
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
    if not await _has_resource_access(request_body, user=requester):
        raise ForbiddenError(
            f"operation not permitted on resource {request_body.resource_id}"
        )

    target_user_ids = await _get_target_user_ids(request_body)
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
        where=And(
            Eq("id", str(pk)),
            Or(
                Eq("target_user_ids", current_user_id),
                Eq("requester_id", current_user_id),
            ),
        ),
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
    sort: Sequence[Sort] = (Sort("created_at", is_descending=True),),
    page: Page = Page(),
) -> List[Request]:
    """Gets the requests the current user made, or those awaiting their decision

    Args:
        database: the database where the requests are stored
        current_user_id: the identifier of the current user
        role: "requester" for the user's own requests, "approver" for those targeting them
        statuses: the statuses of request to return. default = ALL_REQ_STATUSES
        request_types: the types of request to return. default = ALL_REQ_TYPES
        sort: the sort order of the returned results
        page: which slice of the matched requests to return

    Returns:
        the list of request objects
    """
    user_field = "target_user_ids" if role == "approver" else "requester_id"
    where = And(
        Eq(user_field, str(current_user_id)),
        In("status", list(statuses)),
        In("type", list(request_types)),
    )
    return await database.find(Request, where=where, sort=sort, page=page)


async def update(
    database: Database,
    where: Filter,
    payload: RequestUpdate,
    current_user: User,
    sort: Sequence[Sort] = (Sort("created_at", is_descending=True),),
    page: Page = Page(),
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
        database: the database where the requests are stored
        where: the filter the updated requests match
        payload: the update payload for the requests
        current_user: the logged-in user
        sort: the sort order of the returned results
        page: which slice of the matched requests to update

    Returns:
        Returns all updated requests

    Raises:
        NotFoundError: no match found
        NotFoundError: project {id} not found
        NotFoundError: no users of emails {emails}
        ConflictError: a project named '{name}' already exists
    """
    # only pending requests that target the user can be updated
    where = And(
        where,
        Eq("target_user_ids", str(current_user.id)),
        Eq("status", RequestStatus.PENDING),
    )
    # found first, as approving needs them, and update_many can neither skip nor limit
    matches = await database.find(Request, where=where, sort=sort, page=page)
    if len(matches) == 0:
        raise NotFoundError("no match found")

    if payload.status == RequestStatus.APPROVED:
        await actions.do_many_actions(matches, approver=current_user)

    # updated_at is never set by the client, so exclude_unset would drop its default
    update_dict = payload.model_dump(exclude_unset=True)
    update_dict.update(
        {
            "approver_id": str(current_user.id),
            "approver_name": current_user.username,
            "updated_at": payload.updated_at,
        }
    )
    ids = [item.id for item in matches]
    await database.update_many(
        Request,
        where=In("id", ids),
        changes=[Set(field, value) for field, value in update_dict.items()],
    )
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


async def _get_target_user_ids(request: RequestPostBody) -> List[str]:
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
            Project.id == PydanticObjectId(request.resource_id),
            Project.is_personal != True,
            projection_model=_TrimmedProject,
        )
        if project is None:
            raise NotFoundError(f"project {request.resource_id} not found")

        return [str(project.admin_id)]

    elif request.target == RequestTarget.SYSTEM:
        superusers = await User.find({"roles": UserRole.ADMIN}).to_list()
        return [str(user.id) for user in superusers]

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
            Project.id == PydanticObjectId(request.resource_id),
            Project.admin_id == user.id,
            projection_model=_TrimmedProject,
        )
        return project is not None
    elif request.type == RequestType.PROJECT_QPU_SECONDS:
        project = await Project.find_one(
            Project.id == PydanticObjectId(request.resource_id),
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
