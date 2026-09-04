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

"""Routes for the current user's requests, as requester or as approver"""
from enum import Enum
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Query
from fastapi import status as http_status

from api.rest.dependencies import CurrentUserDep
from services.auth import User, user_requests
from services.auth.user_requests import (
    ProjectAccessPostBody,
    UserRequestStatus,
    UserRequestType,
    UserRequestUpdate,
)
from utils.api import PaginatedListResponse

# FIXME: Cleanup the API of requests


router = APIRouter(prefix="/requests", tags=["user-requests"])

RequestCreate = ProjectAccessPostBody


# FIXME: Should never be defined here
class RequestRole(str, Enum):
    """Which side of a request the current user is asking about"""

    REQUESTER = "requester"
    APPROVER = "approver"


@router.post("/", status_code=http_status.HTTP_201_CREATED)
async def create_request(body: RequestCreate, requester: User = CurrentUserDep):
    """Creates a request of the type named in the body

    Currently only `project-access` is creatable here; RFC 0002 adds `create-project`.

    Args:
        body: the request payload, discriminated by its `type` field
        requester: the current signed-in user

    Returns:
        the created user request

    Raises:
        404: no project with ID '{ext_id}'
        409: already a member of, or already has a pending request for, the project
        429: too many pending requests, or too many failed project lookups
    """
    # FIXME: Create project access, yet the requests endpoint is a general term
    result = await user_requests.create_project_access_request(
        body=body, requester=requester
    )
    return result.model_dump(mode="json")


@router.get("/")
async def get_my_requests(
    role: RequestRole = Query(RequestRole.REQUESTER),
    status: Optional[UserRequestStatus] = Query(None),
    types: List[UserRequestType] = Query((), alias="type"),
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
    user: User = CurrentUserDep,
):
    """Gets the requests the current user made, or those awaiting their approval

    Args:
        role: whether to return the user's own requests or those they may react to
        status: the status to filter by; default = None i.e. any
        types: the request types to filter by; repeat the param for many
        skip: the number of records to skip
        limit: the maximum number of records to return
        user: the current signed-in user

    Returns:
        the paginated list of matched requests, newest first
    """
    if role == RequestRole.APPROVER:
        data = await user_requests.get_many_as_approver(
            user, status=status, types=types, skip=skip, limit=limit
        )
    else:
        data = await user_requests.get_many_as_requester(
            str(user.id), status=status, types=types, skip=skip, limit=limit
        )

    return PaginatedListResponse(data=data, skip=skip, limit=limit).model_dump(
        mode="json"
    )


@router.put("/{_id}")
async def react_to_request(
    _id: PydanticObjectId,
    body: UserRequestUpdate,
    user: User = CurrentUserDep,
):
    """Approves or rejects a request the current user is entitled to react to

    Args:
        _id: the unique identifier of the request
        body: the new status, plus a rejection reason if rejecting
        user: the current signed-in user

    Returns:
        the updated user request

    Raises:
        403: you are not entitled to react to this request
        404: {_id} not found
        409: request has already been approved/rejected
    """
    result = await user_requests.update(_id, payload=body, admin_user=user)
    return result.model_dump(mode="json")
