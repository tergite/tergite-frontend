# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Router for my things"""
import logging
from typing import Optional

from fastapi import APIRouter, Query

from api.rest.dependencies import CurrentUserIdDep, MongoDbDep
from services.auth import APP_TOKEN_AUTH, APP_TOKEN_BACKEND
from services.quantum_jobs import JobV1, JobV2, get_latest_many

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


@router.get("/jobs", tags=["jobs"])
async def get_my_jobs_in_project(
    db: MongoDbDep,
    user_id: str = CurrentUserIdDep,
    project_id: Optional[str] = Query(None),
):
    """Retrieves the jobs belonging to the current user in the current project"""
    filters = {"user_id": user_id}
    if project_id is not None:
        filters["project_id"] = project_id
    jobs = await get_latest_many(db, filters=filters)
    return [JobV2.from_v1(JobV1.validate(job)) for job in jobs]
