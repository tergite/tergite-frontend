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

"""Routes for the current user's notifications and their delivery preferences"""
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Query

from services import notifications
from services.auth import User
from services.notifications import (
    ChannelPrefs,
    NotificationRead,
    NotificationType,
    NotificationUpdate,
)
from utils.api import GeneralMessage, PaginatedListResponse

from ..dependencies import CurrentUserDep

router = APIRouter(prefix="/notifications", tags=["notifications"])
prefs_router = APIRouter(prefix="/notification-preferences", tags=["notifications"])


@router.get("/")
async def get_my_notifications(
    types: List[NotificationType] = Query((), alias="type"),
    is_read: Optional[bool] = Query(None),
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
    user: User = CurrentUserDep,
):
    """Gets the current user's notifications, newest first

    Args:
        types: the types to filter by; repeat the param for many
        is_read: filter on read state; default = None i.e. either
        skip: the number of records to skip
        limit: the maximum number of records to return
        user: the current signed-in user

    Returns:
        the paginated list of the user's notifications
    """
    data = await notifications.find_many(
        user.id, types=types, is_read=is_read, skip=skip, limit=limit
    )
    return PaginatedListResponse(
        data=[NotificationRead.model_validate(item) for item in data],
        skip=skip,
        limit=limit,
    ).model_dump(mode="json", exclude_data_none_fields=False)


@router.put("/{pk}")
async def update_my_notification(
    pk: PydanticObjectId, body: NotificationUpdate, user: User = CurrentUserDep
):
    """Marks one of the current user's notifications read or unread

    Args:
        pk: the unique identifier of the notification
        body: the wanted read state
        user: the current signed-in user

    Returns:
        the updated notification

    Raises:
        404: notification of ID '{pk}' not found
    """
    result = await notifications.set_read(pk, user_id=user.id, is_read=body.is_read)
    return NotificationRead.model_validate(result).model_dump(mode="json")


@router.put("/")
async def update_all_my_notifications(
    body: NotificationUpdate, user: User = CurrentUserDep
) -> GeneralMessage:
    """Marks every one of the current user's notifications read or unread

    Args:
        body: the wanted read state
        user: the current signed-in user

    Returns:
        a general message reporting how many were updated
    """
    updated = await notifications.set_all_read(user.id, is_read=body.is_read)
    return {"status": "success", "detail": f"{updated} notifications updated"}


@prefs_router.get("/")
async def get_my_notification_preferences(user: User = CurrentUserDep):
    """Gets the current user's delivery preferences, with defaults filled in

    Args:
        user: the current signed-in user

    Returns:
        a map of notification type to its in-app and email preference
    """
    prefs = await notifications.get_preferences(user.id)
    return {key.value: value.model_dump() for key, value in prefs.items()}


@prefs_router.put("/")
async def update_my_notification_preferences(
    body: Dict[NotificationType, ChannelPrefs], user: User = CurrentUserDep
):
    """Updates the named preferences, leaving the rest untouched

    Types whose in-app channel is mandatory ignore an attempt to silence it.

    Args:
        body: the types to change and their wanted preferences
        user: the current signed-in user

    Returns:
        the user's full effective preferences after the update
    """
    prefs = await notifications.set_preferences(user.id, prefs=body)
    return {key.value: value.model_dump() for key, value in prefs.items()}
