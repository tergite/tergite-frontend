# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Routes for getting counts of different records"""
from datetime import datetime
from typing import Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Query

from api.rest.dependencies import CurrentUserIdDep, CurrentSuperuserDep, MongoDbDep
from services.auth.users.dtos import User
from services import notices as notice_service
from utils.api import CountsResponse

router = APIRouter(prefix="/counts", tags=["counts"])


@router.get("/notices", response_model=CountsResponse)
async def get_notice_count(
    db: MongoDbDep,
    current_user: User = CurrentSuperuserDep,
    user_id: PydanticObjectId = Query(
        None, description="User ID whose notice count is requested"
    ),
    min_start_utc: datetime = Query(None),
    max_start_utc: datetime = Query(None),
    min_expires_utc: datetime = Query(None),
    max_expires_utc: datetime = Query(None),
    include_dismissed: bool = Query(False),
):
    """Gets the number of notices of current user that fulfill a given

    Args:
        current_user: the current logged in user
        user_id: The IDs of the users to retrieve notices for
        min_start_utc: The minimum UTC timestamp the notice should start
        max_start_utc: The maximum UTC timestamp the notice should start
        min_expires_utc: The minimum UTC timestamp the notice should expire
        max_expires_utc: The maximum UTC timestamp the notice should expire
        include_dismissed: whether to include dismissed notices; defaults to False
    """
    # Make sure for ordinary users, the user id is always of the current user
    if not current_user.is_superuser:
        user_id = current_user.id

    return await notice_service.count_many_notices(
        db,
        user_id=user_id,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        min_expires_utc=min_expires_utc,
        max_expires_utc=max_expires_utc,
        include_dismissed=include_dismissed,
    )


@router.get("/job-submitters", response_model=CountsResponse)
async def get_job_submitters_count(
    user_id: str = CurrentUserIdDep,
    start_utc: datetime = Query(...),
    end_utc: datetime = Query(...),
    count_distinct: bool = Query(True),
):
    """Gets the number of notices that fulfill a given filter"""
    raise NotImplementedError()
