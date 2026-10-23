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

from fastapi import APIRouter, Query
from fastapi import status as http_status

from api.rest.dependencies import CurrentUserDep, DatabaseDep
from libs.storage import Eq, Id, Page, parse_sort
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
from utils.api import PaginatedListResponse, build_paginated_json

router = APIRouter()


@router.post(
    "/", status_code=http_status.HTTP_201_CREATED, response_model_by_alias=False
)
async def create(
    database: DatabaseDep, body: RequestPostBody, requester: CurrentUserDep
) -> Request:
    """Creates a request of the type named in the body

    Args:
        body: the request payload, discriminated by its `type` field
        requester: the current signed-in user

    Returns:
        the created user request
    """
    return await requests_service.create(
        database, request_body=body, requester=requester
    )


@router.get("/", responses={200: {"model": PaginatedListResponse[Request]}})
async def get_many(
    database: DatabaseDep,
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
        database: the database where the requests are stored
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
        database,
        current_user_id=user.id,
        role=role,
        statuses=status,
        request_types=types,
        sort=parse_sort(sort),
        page=Page(skip=skip, limit=limit),
    )

    return build_paginated_json(data, skip=skip, limit=limit)


@router.put("/{_id}", response_model_by_alias=False)
async def update(
    database: DatabaseDep,
    _id: Id,
    body: RequestUpdate,
    user: CurrentUserDep,
) -> Request:
    """Updates a request.

    Only approvers can update a request, not requesters.

    Args:
        database: the database where the requests are stored
        _id: the unique identifier of the request
        body: the payload containing new field values
        user: the current signed-in user

    Returns:
        the updated request

    Raises:
        NotFoundError: no pending request of that id awaits the user's decision
    """
    result = await requests_service.update(
        database,
        where=Eq("id", str(_id)),
        payload=body,
        current_user=user,
        page=Page(limit=1),
    )
    return result[0]
