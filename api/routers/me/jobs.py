# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2024, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from api.dependencies import CurrentUserIdDep, DatabaseDep
from services.jobs import Job, JobQuery, get_latest_many
from utils.api import PaginatedListResponse, get_paginated_json

router = APIRouter()


@router.get("/", responses={200: {"model": PaginatedListResponse[Job]}})
async def get_my_jobs(
    database: DatabaseDep,
    user_id: CurrentUserIdDep,
    query: JobQuery = Depends(),
    skip: int = 0,
    limit: Optional[int] = None,
    sort: List[str] = Query(("-created_at",)),
):
    """Gets a paginated list of jobs for the current user that fulfill a given set of filters

    Args:
        database: the database where the jobs are stored
        user_id: the id of the current user
        query: the query params for getting the jobs
        skip: the number of records to skip
        limit: the maximum number of records to return
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ("-created_at",)
            To add multiple fields to sort by, repeat the same query parameter in the url e.g. "query=tom&q=dick&q=harry

    Returns:
        Paginated list of jobs
    """
    data = await get_latest_many(
        database, query, user_id=user_id, sort=sort, skip=skip, limit=limit
    )
    return get_paginated_json(data, skip=skip, limit=limit)
