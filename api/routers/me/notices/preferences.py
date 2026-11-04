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

"""Routes for the current user's notice delivery preferences"""

from typing import Dict

from fastapi import APIRouter

from api.dependencies import CurrentUserIdDep, DatabaseDep
from services import notices as notices_service
from services.notices import NoticeTypeId

router = APIRouter()


@router.get("/")
async def get_my_email_preferences(
    database: DatabaseDep, user_id: CurrentUserIdDep
) -> Dict[NoticeTypeId, bool]:
    """Gets the current user's delivery preferences, with defaults filled in

    Args:
        database: the database where the preferences are stored
        user_id: the ID of the current signed-in user

    Returns:
        a map of notice type to its email preference
    """
    return await notices_service.get_email_preferences(database, user_id)


@router.put("/")
async def update_my_email_preferences(
    database: DatabaseDep, body: Dict[NoticeTypeId, bool], user_id: CurrentUserIdDep
) -> Dict[NoticeTypeId, bool]:
    """Updates the named preferences, leaving the rest untouched

    Args:
        database: the database where the preferences are stored
        body: the types to change and their wanted preferences
        user_id: the ID of the current signed-in user

    Returns:
        the user's full effective preferences after the update
    """
    return await notices_service.set_email_preferences(
        database, user_id=user_id, prefs=body
    )
