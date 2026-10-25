# This code is part of Tergite
#
# (C) Copyright Miroslav Dobsicek 2020
# (C) Copyright Simon Genne, Arvid Holmqvist, Bashar Oumari, Jakob Ristner,
#               Björn Rosengren, and Jakob Wik 2022 (BSc project)
# (C) Copyright Fabian Forslund, Niklas Botö 2022
# (C) Copyright Abdullah-Al Amin 2022
# (C) Copyright Martin Ahindura 2023
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.requests import Request

from api.dependencies import (
    CurrentLaxOwnerDep,
    CurrentStrictProjectUserIdsDep,
    CurrentUserDep,
    DatabaseDep,
    RequestIdDep,
)
from services import jobs as jobs_service
from services.external import bcc
from services.external.bcc import CancellationDetails
from services.jobs import (
    CreatedJobResponse,
    Job,
    JobCreate,
    JobQuery,
    JobStatusResponse,
)
from utils.api import GeneralMessage, PaginatedListResponse, get_paginated_json

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", responses={200: {"model": PaginatedListResponse[Job]}})
async def get_many(
    database: DatabaseDep,
    owner: CurrentLaxOwnerDep,
    query: JobQuery = Depends(),
    skip: int = 0,
    limit: Optional[int] = None,
    sort: List[str] = Query(("-created_at",)),
):
    """Gets a paginated list of jobs that fulfill a given set of filters

    Args:
        database: the database where the jobs are stored
        owner: the API token's project and user; only the user's jobs, jobs with no recorded user, or all jobs for an admin are listed
        query: the query params for getting the jobs
        skip: the number of records to skip
        limit: the maximum number of records to return
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ("-created_at",)
            To add multiple fields to sort by, repeat the same query parameter in the url e.g. "query=tom&q=dick&q=harry"
    """
    data = await jobs_service.get_latest_many(
        database, query, reader=owner.user, sort=sort, skip=skip, limit=limit
    )
    return get_paginated_json(data, skip=skip, limit=limit)


@router.get("/{job_id}", responses={200: {"model": Job}})
async def get_one(database: DatabaseDep, owner: CurrentLaxOwnerDep, job_id: UUID):
    """Gets the job of the given job_id

    Args:
        database: the database where the jobs are stored
        owner: the API token's project and user; the user must have submitted the job or be an admin
        job_id: the job_id of the job
    """
    return await jobs_service.get_readable_job(
        database, job_id=job_id, user=owner.user, should_decrypt_token=True
    )


@router.get("/{job_id}/status")
async def get_job_status(
    database: DatabaseDep, owner: CurrentLaxOwnerDep, job_id: UUID
) -> JobStatusResponse:
    """Gets the status of the job for the given job_id

    Args:
        database: the database where the jobs are stored
        owner: the API token's project and user; the user must have submitted the job or be an admin
        job_id: the ID of the job

    Returns:
        the status as one value

    Raises:
        utils.exc.NotFoundError: no matches for '{search_filter}'.
        ValidationError: the document does not satisfy the schema passed
    """
    job = await jobs_service.get_readable_job(database, job_id=job_id, user=owner.user)
    return JobStatusResponse.from_job(job)


@router.post("/")
async def create_one(
    request: Request,
    database: DatabaseDep,
    project_user_id_pair: CurrentStrictProjectUserIdsDep,
    payload: JobCreate,
    request_id: RequestIdDep,
) -> CreatedJobResponse:
    """Creates a job in the given backend and given calibration_date in the body"""
    project_id, user_id = project_user_id_pair
    return await jobs_service.create_job(
        database,
        bcc_client=bcc.get_client(payload.device),
        payload=payload,
        project_id=project_id,
        user_id=user_id,
        request_id=request_id,
    )


@router.post("/{job_id}/cancel")
async def cancel_job(
    database: DatabaseDep,
    job_id: UUID,
    details: CancellationDetails,
    request_id: RequestIdDep,
    user: CurrentUserDep,
) -> GeneralMessage:
    """Cancels the job of given job_id if job belongs to current user or if user is admin

    Args:
        database: the database where the jobs are stored
        job_id: the unique identifier of the job
        details: the extra information passed when canceling the job
        request_id: the request id associated with this request
        user: the current logged-in user

    Returns:
        a general message showing status
    Raises:
        401: user not found
        404: Job {job_id} not found
        404: no matches for {job_id: job_id}
        406: if the job has already been cancelled
    """
    job = await jobs_service.get_job(database, job_id=job_id)
    return await jobs_service.cancel_job(
        database,
        bcc_client=bcc.get_client(job.device),
        job_id=job_id,
        user_id=user.id,
        request_id=request_id,
        details=details,
    )


@router.delete("/{job_id}")
async def remove_job(
    database: DatabaseDep,
    job_id: UUID,
    request_id: RequestIdDep,
    user: CurrentUserDep,
) -> GeneralMessage:
    """Deletes the job of given job_id if job belongs to current user or if user is admin

    Args:
        database: the database where the jobs are stored
        job_id: the unique identifier of the job
        request_id: the request id associated with this request
        user: the logged-in user

    Returns:
        a general message showing status
    Raises:
        401: user not found
        404: Job {job_id} not found
        404: no matches for {job_id: job_id}
    """
    job = await jobs_service.get_job(database, job_id=job_id)
    return await jobs_service.delete_job(
        database,
        bcc_client=bcc.get_client(job.device),
        job_id=job_id,
        user_id=user.id,
        request_id=request_id,
    )
