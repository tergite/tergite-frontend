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
from typing import Dict

from fastapi import APIRouter

from api.rest.dependencies import CurrentUserIdDep
from services import notices as notices_service
from services.notices import NoticeType

router = APIRouter(prefix="/preferences", tags=["notices-preferences"])


@router.get("/")
async def get_my_email_preferences(user_id: str = CurrentUserIdDep):
    """Gets the current user's delivery preferences, with defaults filled in

    Args:
        user_id: the ID of the current signed-in user

    Returns:
        a map of notice type to its email preference
    """
    return await notices_service.get_email_preferences(user_id)


@router.put("/")
async def update_my_email_preferences(
    body: Dict[NoticeType, bool], user_id: str = CurrentUserIdDep
):
    """Updates the named preferences, leaving the rest untouched

    Args:
        body: the types to change and their wanted preferences
        user_id: the ID of the current signed-in user

    Returns:
        the user's full effective preferences after the update
    """
    return await notices_service.set_email_preferences(user_id=user_id, prefs=body)
