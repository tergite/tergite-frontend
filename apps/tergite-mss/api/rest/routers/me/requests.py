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

from typing import Optional, Tuple

from beanie import PydanticObjectId
from fastapi import APIRouter, Query
from fastapi import status as http_status

from api.rest.dependencies import CurrentUserDep
from services import requests as requests_service
from services.requests import (
    ALL_REQ_STATUSES,
    ALL_REQ_TYPES,
    Request,
    RequestPostBody,
    RequestRole,
    RequestStatus,
    RequestType,
    RequestUpdate,
)
from utils.api import PaginatedListResponse

router = APIRouter()


@router.post(
    "/", status_code=http_status.HTTP_201_CREATED, response_model_by_alias=False
)
async def create(body: RequestPostBody, requester: CurrentUserDep) -> Request:
    """Creates a request of the type named in the body

    Args:
        body: the request payload, discriminated by its `type` field
        requester: the current signed-in user

    Returns:
        the created user request
    """
    return await requests_service.create(request_body=body, requester=requester)


@router.get("/")
async def get_many(
    user: CurrentUserDep,
    role: RequestRole = Query("approver"),
    status: Tuple[RequestStatus, ...] = Query(ALL_REQ_STATUSES),
    types: Tuple[RequestType, ...] = Query(ALL_REQ_TYPES, alias="type"),
    sort: tuple[str, ...] = Query(("-created_at",)),
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
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
    data = await requests_service.get_many(
        current_user_id=user.id,
        role=role,
        statuses=status,
        request_types=types,
        skip=skip,
        sort=sort,
        limit=limit,
    )

    return PaginatedListResponse(data=data, skip=skip, limit=limit).model_dump(
        mode="json"
    )


@router.put("/{_id}", response_model_by_alias=False)
async def update(
    _id: PydanticObjectId,
    body: RequestUpdate,
    user: CurrentUserDep,
) -> Request:
    """Updates a request.

    Only approvers can update a request, not requesters.

    Args:
        _id: the unique identifier of the request
        body: the payload containing new field values
        user: the current signed-in user

    Returns:
        the updated request

    Raises:
        NotFoundError: no pending request of that id awaits the user's decision
    """
    result = await requests_service.update(
        {"_id": _id}, payload=body, current_user=user, limit=1
    )
    return result[0]
