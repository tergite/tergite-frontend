# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Router for my things"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from api.rest.dependencies import CurrentUserDep, CurrentUserIdDep, MongoDbDep
from api.rest.routers.requests import router as requests_router
from services.auth import APP_TOKEN_AUTH, APP_TOKEN_BACKEND, User, UserRead
from services.jobs import get_latest_many
from services.jobs.dtos import JobQuery
from utils.api import PaginatedListResponse

router = APIRouter(prefix="/me")

router.include_router(
    APP_TOKEN_AUTH.get_my_projects_router(),
    prefix="/projects",
    tags=["auth"],
)

router.include_router(
    APP_TOKEN_AUTH.get_app_tokens_router(backend=APP_TOKEN_BACKEND),
    prefix="/tokens",
    tags=["auth"],
)

router.include_router(requests_router)


@router.get("/jobs/", tags=["jobs"])
async def get_my_jobs(
    db: MongoDbDep,
    user_id: str = CurrentUserIdDep,
    query: JobQuery = Depends(),
    skip: int = 0,
    limit: Optional[int] = None,
    sort: List[str] = Query(("-created_at",)),
):
    """Gets a paginated list of jobs for the current user that fulfill a given set of filters

    Args:
        db: the mongo db database from which to get the job
        user_id: the id of the current user
        query: the query params for getting the jobs
        skip: the number of records to skip
        limit: the maximum number of records to return
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ("-created_at",)
            To add multiple fields to sort by, repeat the same query parameter in the url e.g. "query=tom&q=dick&q=harry

    Returns:
        Paginated list of jobs
    """
    filters = query.model_dump()
    # ensure that only jobs for the current user are considered
    filters["user_id"] = user_id

    data = await get_latest_many(
        db,
        filters=filters,
        limit=limit,
        sort=sort,
        skip=skip,
    )
    return PaginatedListResponse(skip=skip, limit=limit, data=data).model_dump(
        mode="json"
    )


@router.get("", tags=["users"], response_model=UserRead)
async def get_my_user_info(user: User = CurrentUserDep):
    """Retrieves the information on the current user"""
    return user.model_dump()
