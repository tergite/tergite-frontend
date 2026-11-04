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

"""Routes for the current user's notices"""

from typing import List, Optional

from fastapi import APIRouter, Query

from api.dependencies import CurrentUserDep, CurrentUserIdDep, DatabaseDep
from libs.storage import Id
from services import notices as notices_service
from services.notices import Notice, NoticeQuery, NoticeTypeId
from utils.api import GeneralMessage, PaginatedListResponse, get_paginated_json

router = APIRouter()


@router.get("/", responses={200: {"model": PaginatedListResponse[Notice]}})
async def get_my_notices(
    database: DatabaseDep,
    user_id: CurrentUserIdDep,
    types: List[NoticeTypeId] = Query((), alias="type"),
    is_read: Optional[bool] = Query(None),
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
):
    """Gets the current user's notices, newest first

    Args:
        database: the database where the notices are stored
        user_id: the ID of the current signed-in user
        types: the types to filter by; repeat the param for many
        is_read: filter on read state; default = None i.e. either
        skip: the number of records to skip
        limit: the maximum number of records to return

    Returns:
        the paginated list of the user's notices
    """
    query = NoticeQuery(
        user_id=user_id, should_include_dismissed=True, types=types, is_read=is_read
    )
    data = await notices_service.find_many(
        database, query=query, sort=["-created_at"], skip=skip, limit=limit
    )
    return get_paginated_json(data, skip=skip, limit=limit, should_exclude_none=False)


@router.post("/{notice_id}/dismiss")
async def dismiss_my_notice(
    database: DatabaseDep,
    notice_id: Id,
    current_user: CurrentUserDep,
) -> GeneralMessage:
    """Dismisses a notice

    Args:
        database: the database where the notices are stored
        notice_id: the unique identifier of the notice
        current_user: the current logged-in user

    Returns:
        a general message about the status of the operation

    Raises:
        404: notification of ID '{pk}' not found
    """
    await notices_service.set_read_status(
        database, pk=notice_id, user_id=current_user.id, is_read=True
    )
    return {"status": "success"}


@router.post("/{notice_id}/unread")
async def unread_my_notice(
    database: DatabaseDep,
    notice_id: Id,
    current_user: CurrentUserDep,
) -> GeneralMessage:
    """Marks a notice unread

    Args:
        database: the database where the notices are stored
        notice_id: the unique identifier of the notice
        current_user: the current logged-in user

    Returns:
        a general message about the status of the operation

    Raises:
        404: notification of ID '{pk}' not found
    """
    await notices_service.set_read_status(
        database, pk=notice_id, user_id=current_user.id, is_read=False
    )
    return {"status": "success"}


@router.post("/dismiss")
async def dismiss_all_my_notices(
    database: DatabaseDep,
    user_id: CurrentUserIdDep,
) -> GeneralMessage:
    """Marks every one of the current user's notices read

    Args:
        database: the database where the notices are stored
        user_id: the ID of the current signed-in user

    Returns:
        a general message reporting how many were updated
    """
    counts = await notices_service.set_read_status_many(
        database, user_id=user_id, is_read=True
    )
    return {"status": "success", "detail": f"{counts} notices updated"}


@router.post("/unread")
async def unread_all_my_notices(
    database: DatabaseDep,
    user_id: CurrentUserIdDep,
) -> GeneralMessage:
    """Marks every one of the current user's notices unread

    Args:
        database: the database where the notices are stored
        user_id: the ID of the current signed-in user

    Returns:
        a general message reporting how many were updated
    """
    counts = await notices_service.set_read_status_many(
        database, user_id=user_id, is_read=False
    )
    return {"status": "success", "detail": f"{counts} notices updated"}
