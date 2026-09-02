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

"""Routes for the current user's notices and their delivery preferences"""
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Query

from services import notices
from services.notices import (
    Notice,
    NoticeType,
)
from utils.api import GeneralMessage, PaginatedListResponse

from ..dependencies import CurrentUserIdDep, MongoDbDep

router = APIRouter(prefix="/notices", tags=["notices"])
prefs_router = APIRouter(
    prefix="/notice-preferences", tags=["notices", "notice-preferences"]
)

# FIXME: Move these to /me


@router.get("/")
async def get_my_notices(
    db: MongoDbDep,
    types: List[NoticeType] = Query((), alias="type"),
    is_read: Optional[bool] = Query(None),
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
    user_id: str = CurrentUserIdDep,
):
    """Gets the current user's notices, newest first

    Args:
        db: the mongodb instance that stores the data
        types: the types to filter by; repeat the param for many
        is_read: filter on read state; default = None i.e. either
        skip: the number of records to skip
        limit: the maximum number of records to return
        user_id: the ID of the current signed-in user

    Returns:
        the paginated list of the user's notices
    """
    data = await notices.find_many_notices(
        db,
        user_id=PydanticObjectId(user_id),
        types=types,
        skip=skip,
        limit=limit,
        is_read=is_read,
        include_dismissed=True,
    )
    PaginatedListResponse(skip=skip, limit=limit, data=data).model_dump(
        mode="json", exclude_data_none_fields=False
    )


@router.put("/{pk}")
async def toggle_notice_read_status(
    db: MongoDbDep,
    pk: PydanticObjectId,
    user_id: str = CurrentUserIdDep,
    is_read: Optional[bool] = Query(True),
):
    """Marks one of the current user's notices read or unread

    Args:
        db: the mongodb instance that stores the data
        pk: the unique identifier of the notification
        user_id: the ID of the current signed-in user
        is_read: whether to mark is read or unread; default = True i.e. read

    Returns:
        the updated notification

    Raises:
        404: notification of ID '{pk}' not found
    """
    result = await notices.toggle_notice_read_status(
        db, pk=pk, user_id=PydanticObjectId(user_id), is_read=is_read
    )
    return Notice.model_validate(result).model_dump(mode="json")


@router.put("/")
async def toggle_all_my_notices_read_status(
    db: MongoDbDep,
    user_id: str = CurrentUserIdDep,
    is_read: Optional[bool] = Query(True),
) -> GeneralMessage:
    """Marks every one of the current user's notices read or unread

    Args:
        db: the mongodb instance that stores the data
        user_id: the ID of the current signed-in user
        is_read: whether to mark is read or unread; default = True i.e. read

    Returns:
        a general message reporting how many were updated
    """
    counts = await notices.toggle_notice_read_status_many(
        db, user_id=PydanticObjectId(user_id), is_read=is_read
    )
    return {"status": "success", "detail": f"{counts} notices updated"}


@prefs_router.get("/")
async def get_my_email_notice_preferences(user_id: str = CurrentUserIdDep):
    """Gets the current user's delivery preferences, with defaults filled in

    Args:
        user_id: the ID of the current signed-in user

    Returns:
        a map of notice type to its email preference
    """
    return await notices.get_email_preferences(PydanticObjectId(user_id))


@prefs_router.put("/")
async def update_my_email_notice_preferences(
    body: Dict[NoticeType, bool], user_id: str = CurrentUserIdDep
):
    """Updates the named preferences, leaving the rest untouched

    Args:
        body: the types to change and their wanted preferences
        user_id: the ID of the current signed-in user

    Returns:
        the user's full effective preferences after the update
    """
    return await notices.set_email_preferences(
        user_id=PydanticObjectId(user_id), prefs=body
    )
