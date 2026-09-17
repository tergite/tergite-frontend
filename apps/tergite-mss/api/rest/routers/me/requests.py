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

from typing import Optional, Literal, Tuple

from beanie import PydanticObjectId
from fastapi import APIRouter, Query
from fastapi import status as http_status

from api.rest.dependencies import CurrentUserDep
from services import requests as requests_service
from services.auth import User
from services.requests import (
    RequestPostBody,
    RequestStatus,
    RequestType,
    RequestUpdate,
)
from services.requests.service import ALL_REQ_TYPES, ALL_REQ_STATUSES
from utils.api import PaginatedListResponse
from utils.exc import NotFoundError


router = APIRouter(prefix="/requests", tags=["user-requests"])


@router.post("/", status_code=http_status.HTTP_201_CREATED)
async def create(body: RequestPostBody, requester: User = CurrentUserDep):
    """Creates a request of the type named in the body

    Currently only `project-access` is creatable here; RFC 0002 adds `create-project`.

    Args:
        body: the request payload, discriminated by its `type` field
        requester: the current signed-in user

    Returns:
        the created user request
    """
    # FIXME: Create project access, yet the requests endpoint is a general term
    return await requests_service.create(request_body=body, requester=requester)


@router.get("/")
async def get_many(
    role: Literal["requester", "approver"] = Query("approver"),
    status: Tuple[RequestStatus, ...] = Query(ALL_REQ_STATUSES),
    types: Tuple[RequestType, ...] = Query(ALL_REQ_TYPES, alias="type"),
    sort: tuple[str, ...] = Query(("-created_at",)),
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
    user: User = CurrentUserDep,
):
    """Gets the requests the current user made, or those awaiting their approval

    Args:
        role: whether to return the user's own requests or those they may react to
        status: the status to filter by; default = ALL_REQ_STATUSES i.e. any
        types: the request types to filter by; repeat the param for many; default = ALL_REQ_TYPES
        sort: the fields to sort by and in what direction, '-' meaning descending order; default = -created_at
        skip: the number of records to skip
        limit: the maximum number of records to return
        user: the current signed-in user

    Returns:
        the paginated list of matched requests, newest first
    """
    filter_obj: dict = {"status": {"$in": status}}
    if role == "approver":
        filter_obj["target_user_ids"] = user.id
    else:
        filter_obj["requester_id"] = user.id

    data = await requests_service.get_many(
        filter_obj,
        current_user_id=user.id,
        request_types=types,
        skip=skip,
        sort=sort,
        limit=limit,
    )

    return PaginatedListResponse(data=data, skip=skip, limit=limit).model_dump(
        mode="json"
    )


@router.put("/{_id}")
async def update(
    pk: PydanticObjectId,
    body: RequestUpdate,
    user: User = CurrentUserDep,
):
    """Updates a request.

    Only approvers can update a request, not requesters.

    Args:
        pk: the unique identifier of the request
        body: the payload containing new field values
        user: the current signed-in user

    Returns:
        the updated request

    Raises:
        404: {_id} not found
    """
    result = await requests_service.update({"_id": pk}, payload=body, current_user=user, limit=1)
    if len(result) == 0:
        raise NotFoundError(f"{pk} not found")

    return result[0]
