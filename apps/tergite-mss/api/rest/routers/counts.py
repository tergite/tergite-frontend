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
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Query

from api.rest.dependencies import (
    CurrentSuperuserDep,
    CurrentUserDep,
    DatabaseDep,
)
from services import jobs as jobs_service
from services import notices as notices_service
from services.notices import NoticeTypeId
from utils.api import CountsResponse

router = APIRouter(prefix="/counts", tags=["counts"])


@router.get("/notices")
async def get_notice_count(
    database: DatabaseDep,
    current_user: CurrentUserDep,
    user_id: PydanticObjectId = Query(
        None, description="User ID whose notice count is requested"
    ),
    min_start_utc: datetime = Query(None),
    max_start_utc: datetime = Query(None),
    min_expires_utc: datetime = Query(None),
    max_expires_utc: datetime = Query(None),
    include_dismissed: bool = Query(False),
    types: List[NoticeTypeId] = Query((), alias="type"),
    is_read: Optional[bool] = Query(None),
) -> CountsResponse:
    """Gets the number of notices that fulfill the given filters

    Args:
        database: the database where the notices are stored
        current_user: the current logged in user
        user_id: The IDs of the users to retrieve notices for; only superusers can set it
        min_start_utc: The minimum UTC timestamp the notice should start
        max_start_utc: The maximum UTC timestamp the notice should start
        min_expires_utc: The minimum UTC timestamp the notice should expire
        max_expires_utc: The maximum UTC timestamp the notice should expire
        include_dismissed: whether to include dismissed notices; defaults to False
        types: the types to filter by; repeat the param for many
        is_read: filter on read state; default = None i.e. either
    """
    count = await notices_service.count_many(
        database,
        requester=current_user,
        user_id=user_id,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        min_expires_utc=min_expires_utc,
        max_expires_utc=max_expires_utc,
        should_include_dismissed=include_dismissed,
        types=types,
        is_read=is_read,
    )
    return {"count": count}


@router.get(
    "/job-submitters",
    response_model=CountsResponse,
)
async def get_job_submitters_count(
    database: DatabaseDep,
    requester: CurrentSuperuserDep,
    start_utc: datetime = Query(...),
    end_utc: datetime = Query(...),
    should_count_distinct: bool = Query(True, alias="count_distinct"),
) -> CountsResponse:
    """Gets the number of users who submitted jobs in [start_utc, end_utc), for admins only

    Args:
        database: the database where the jobs are stored
        requester: the superuser making the request; anyone else gets a 403
        start_utc: the start of the window, inclusive
        end_utc: the end of the window, exclusive
        should_count_distinct: whether to count each submitter once; otherwise every job counts
    """
    count = await jobs_service.count_job_submitters(
        database,
        start_utc=start_utc,
        end_utc=end_utc,
        should_count_distinct=should_count_distinct,
    )
    return {"count": count}
