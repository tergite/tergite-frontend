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
"""Runs a job the dashboard submits as text: OpenQASM 3 circuits, sent on to the backend

MSS creates the job as for the SDK and uploads the job file to the backend itself, so a
browser never talks to a backend; the backend reads the circuits and refuses at upload one it
cannot run.
"""

from loguru import logger

from libs.storage import Database
from services.external import bcc
from utils.exc import BccHttpError, InvalidCircuitError, ServiceUnavailableError

from ..auth import (
    STRICT,
    Project,
    TokenOwner,
    User,
    check_project_access,
    get_project_if_member,
)
from .dtos import Job, JobCreate, JobFile, JobSource, JobSubmission
from .service import create_job, get_job

# the submission's fields that are the job's source, without where it runs or who pays
SOURCE_FIELDS = set(JobSource.model_fields)


async def submit_job(
    database: Database,
    submission: JobSubmission,
    user: User,
    calibration_date: str,
) -> Job:
    """Creates the submitted circuits' job and uploads it to the backend, which reads them

    Args:
        database: the database where the jobs and projects are stored
        submission: the circuits, their settings, the device and the project
        user: the user submitting
        calibration_date: when the device was last calibrated

    Returns:
        the job, pending

    Raises:
        UnauthorizedError: the project is inactive, or the user is not its member
        ForbiddenError: the project has no QPU seconds left
        UnknownBccError: MSS knows no backend for the device
        InvalidCircuitError: a circuit the backend cannot run; the job is not kept
        ServiceUnavailableError: the device is unavailable; the job is not kept
        BccHttpError: the backend refused the job file otherwise; the job is not kept
    """
    project = await _get_project_with_qpu(database, submission.project_id, user)
    bcc_client = bcc.get_client(submission.device)
    created = await create_job(
        database,
        bcc_client=bcc_client,
        payload=JobCreate(device=submission.device, calibration_date=calibration_date),
        project_id=project.id,
        user_id=str(user.id),
    )
    job_id = created["job_id"]
    source = JobSource.model_validate(submission.model_dump(include=SOURCE_FIELDS))

    job_file = JobFile.from_source(job_id, source)
    try:
        await bcc_client.upload_job(
            job_id, job_file.model_dump_json(), token=created["access_token"]
        )
    except (InvalidCircuitError, BccHttpError, ServiceUnavailableError):
        # the backend never took it, so there is no job to show
        await database.delete_one(Job, {"job_id": job_id})
        raise

    await database.update_one(
        Job, {"job_id": job_id}, {"$set": {"source": source.model_dump()}}
    )
    logger.info(f"Job {job_id} submitted from the dashboard by user {user.id}")
    job = await get_job(database, job_id=job_id)
    return job.model_copy(update={"access_token": None})


async def _get_project_with_qpu(
    database: Database, project_id: str, user: User
) -> Project:
    """The project, if the user is its member and it may run jobs, as an app token's must"""
    project = await get_project_if_member(database, project_id, str(user.id))
    owner = None if project is None else TokenOwner(project=project, user=user)
    return check_project_access(owner, STRICT).project
