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
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from api.dependencies import CurrentUserDep, CurrentUserIdDep, DatabaseDep
from services import calibration as calibration_service
from services import devices as devices_service
from services import jobs as jobs_service
from services.external import bcc
from services.jobs import Job, JobQuery, JobSubmission
from utils.api import PaginatedListResponse, get_paginated_json
from utils.exc import InvalidCircuitError, InvalidInputError, NotFoundError

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
    data = await jobs_service.get_latest_many(
        database, query, user_id=user_id, sort=sort, skip=skip, limit=limit
    )
    return get_paginated_json(data, skip=skip, limit=limit)


@router.post("/", status_code=201)
async def submit_my_job(
    database: DatabaseDep, user: CurrentUserDep, payload: JobSubmission
) -> Job:
    """Runs OpenQASM 3 circuits on a device, as a job billed to one of the user's projects

    MSS uploads the job to the device's backend itself; the backend reads the circuits and
    refuses one it cannot run, and a job it refuses is not kept.

    Args:
        database: the database where the jobs, projects and devices are stored
        user: the current user
        payload: the circuits, their settings, the device and the project

    Returns:
        the job, pending

    Raises:
        401: the project is inactive, or the user is not its member
        400: MSS knows no backend for the device, or the device has no calibration, or
            the backend refused the job file otherwise, e.g. beyond its pulse limits
        403: the project has no QPU seconds left, or may not send pulse-level programs
        404: no such device
        422: a circuit the backend cannot run, at body.circuits.<index>.qasm, with the line
            and column, from 1, in its ctx when known
        503: the device is unavailable
    """
    await devices_service.get_device(database, payload.device)
    try:
        calibration = await calibration_service.get_one(database, payload.device)
    except NotFoundError:
        raise InvalidInputError(f"{payload.device} has no calibration yet")

    try:
        return await jobs_service.submit_job(
            database,
            submission=payload,
            user=user,
            calibration_date=calibration.last_calibrated,
        )
    except InvalidCircuitError as exp:
        raise RequestValidationError([_to_validation_error(exp)])


@router.get("/{job_id}")
async def get_my_job(database: DatabaseDep, user: CurrentUserDep, job_id: UUID) -> Job:
    """Gets one of the user's jobs, with its source if it was submitted from the dashboard

    Args:
        database: the database where the jobs are stored
        user: the current user
        job_id: the id of the job

    Returns:
        the job, without its backend token

    Raises:
        404: no such job, or not the user's
    """
    job = await jobs_service.get_readable_job(database, job_id=job_id, user=user)
    return job.model_copy(update={"access_token": None})


@router.get(
    "/{job_id}/logfile",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/x-hdf5": {}}}},
)
async def get_my_job_logfile(
    database: DatabaseDep, user: CurrentUserDep, job_id: UUID
) -> StreamingResponse:
    """Downloads one of the user's jobs' logfile, which MSS fetches from the backend

    Args:
        database: the database where the jobs are stored
        user: the current user
        job_id: the id of the job

    Returns:
        the job's HDF5 logfile

    Raises:
        404: no such job, not the user's, or it has no logfile yet
        503: the device is unavailable
    """
    job = await jobs_service.get_readable_job(
        database, job_id=job_id, user=user, should_decrypt_token=True
    )
    if not job.download_url or not job.access_token:
        raise NotFoundError(f"job {job_id} has no logfile yet")

    response = await bcc.get_client(job.device).open_logfile(
        job.download_url, token=job.access_token
    )
    return StreamingResponse(
        response.aiter_bytes(),
        media_type="application/x-hdf5",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.hdf5"'},
        background=BackgroundTask(response.aclose),
    )


def _to_validation_error(exp: InvalidCircuitError) -> dict:
    """The error as FastAPI words a validation error, placed at the circuit's text"""
    return {
        "type": "invalid_circuit",
        "loc": ("body", "circuits", exp.index, "qasm"),
        "msg": exp.message,
        "input": None,
        "ctx": {"line": exp.line, "column": exp.column},
    }
