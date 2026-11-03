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
from datetime import datetime
from typing import List, Optional, Sequence, Tuple
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from loguru import logger

from libs.storage import Database, Returning
from services import notices
from services.external.bcc import BccClient, CancellationDetails
from utils.api import GeneralMessage
from utils.config import ProjectsConfig
from utils.crypto import decrypt_message
from utils.date_time import datetime_to_zulu, get_current_timestamp
from utils.exc import NotFoundError

from ..auth import Project, User, increment_qpu_seconds
from ..notices import NoticeTypeId
from ..notices.dtos import ProjectRequestContext, RefType
from .dtos import CreatedJobResponse, Job, JobCreate, JobQuery, JobStatus, JobUpdate

# on_startup replaces these with what the app is configured with
_private_key: Optional[RSAPrivateKey] = None
_qpu_seconds_low_threshold = ProjectsConfig().qpu_seconds_low_threshold


async def get_job(
    database: Database,
    job_id: UUID,
    should_decrypt_token: bool = False,
) -> Job:
    """Gets a job by job_id

    Args:
        database: the database where the jobs are stored
        job_id: the `job_id` of the job to be returned
        should_decrypt_token: whether to decrypt the returned access token

    Raises:
        utils.exc.NotFoundError: no matches for '{search_filter}'.
        ValidationError: the document does not satisfy the schema passed

    Returns:
        the job as a dict
    """
    result = await database.get(Job, str(job_id))
    if result is None:
        raise NotFoundError(f"no matches for '{ {'job_id': str(job_id)} }'")
    if should_decrypt_token and result.access_token:
        result.access_token = decrypt_message(_private_key, msg=result.access_token)

    return result


async def create_job(
    database: Database,
    bcc_client: BccClient,
    payload: JobCreate,
    project_id: Optional[str],
    user_id: Optional[str],
) -> CreatedJobResponse:
    """Creates a new job for the given backend

    Args:
        database: the database where the jobs are stored
        bcc_client: the HTTP client for accessing BCC
        payload: the job to create
        project_id: the unique identifier of the project the job is billed to
        user_id: the unique identifier of the user

    Returns:
        the created job details

    Raises:
            ValueError: job id '{job_id}' already exists
                See :meth:`utils.http_clients.BccClient.save_credentials`
            ServiceUnavailableError: device is currently unavailable.
                See :meth:`utils.http_clients.BccClient.save_credentials`
    """
    job = Job(
        **payload.model_dump(),
        project_id=None if project_id is None else str(project_id),
        user_id=None if user_id is None else str(user_id),
    )
    logger.info(f"Creating new job with id: {job.job_id} for user: {user_id}")
    project = None if project_id is None else await database.get(Project, project_id)
    encrypted_token, token = await bcc_client.get_token(
        job_id=job.job_id,
        user_id=user_id,
        is_pulse_allowed=project is not None and project.is_pulse_allowed,
    )
    job.access_token = encrypted_token
    await database.insert(Job, job)
    logger.debug(f"Job {job.job_id} successfully saved to database")

    return {
        "job_id": job.job_id,
        "upload_url": f"{bcc_client.public_base_url}/jobs",
        "access_token": token,
    }


async def get_latest_many(
    database: Database,
    query: JobQuery,
    user_id: Optional[str] = None,
    reader: Optional[User] = None,
    sort: Sequence[str] = (),
    skip: int = 0,
    limit: Optional[int] = None,
    exclude: Tuple[str, ...] = ("access_token",),
) -> List[Job]:
    """Retrieves the latest jobs up to the given limit

    By default, the access_token is not returned when many jobs are requested for.
    This is because such requests are usually not to submit the job but rather to view it.

    Args:
        database: the database where the jobs are stored
        query: the values every returned job has; its unset fields match anything
        user_id: the user whose jobs alone are wanted, in place of the query's user_id
        reader: the user reading the jobs; only those they may read are returned
        sort: the fields to sort by; a leading '-' sorts descending
        skip: the number of matched jobs to skip
        limit: the most jobs to return; None returns all
        exclude: the fields to leave out of each job

    Returns:
        the matching jobs, with the excluded fields set to None
    """
    job_filter = query.model_dump(
        exclude_unset=True, exclude_defaults=True, exclude_none=True
    )
    if user_id is not None:
        job_filter["user_id"] = str(user_id)
    if reader is not None and not reader.is_superuser:
        readable_filter = {"user_id": {"$in": [str(reader.id), None]}}
        job_filter = {"$and": [job_filter, readable_filter]}

    jobs = await database.find(
        Job, filter=job_filter, sort=sort, skip=skip, limit=limit
    )
    return [job.model_copy(update={field: None for field in exclude}) for job in jobs]


async def update_job(database: Database, job_id: str, payload: JobUpdate) -> Job:
    """Updates the job of the given job_id

    Args:
        database: the database where the jobs are stored
        job_id: the job id of the job
        payload: the new payload to update in job

    Returns:
        the job before it was modified

    Raises:
        NotFoundError: no documents matching {"job_id": job_id} were found
    """
    job = await database.update_one(
        Job,
        filter={"job_id": job_id},
        update={
            "$set": {
                **payload.model_dump(
                    exclude_unset=True, exclude_defaults=True, exclude_none=True
                ),
                "updated_at": get_current_timestamp(),
            }
        },
        returning=Returning.BEFORE,
    )
    if job is None:
        raise NotFoundError(f"no matches for { {'job_id': job_id} }")
    return job


async def update_qpu_usage(
    database: Database,
    job_id: UUID,
    qpu_usage: float,
) -> Optional[Project]:
    """Updates the resource usage for the job of the given job_id

    Args:
        database: the database where the jobs and projects are stored
        job_id: the job id of the job
        qpu_usage: the resource usage in seconds

    Returns:
        the updated project if the job was attached to a project, else None

    Raises:
        utils.exc.NotFoundError: no matches for '{"job_id": job_id}'.
        utils.exc.NotFoundError: project '{project_id}' for job '{job_id}' not found
        KeyError: 'project_id'
    """
    job = await get_job(database, job_id=job_id)
    project_id = job.project_id
    project = await increment_qpu_seconds(
        database, project_id=project_id, qpu_seconds=-qpu_usage
    )
    if project is None:
        if project_id is not None:
            raise NotFoundError(f"project '{project_id}' for job '{job_id}' not found")
        return project

    notice_type = _choose_qpu_notice(
        before=project.qpu_seconds + qpu_usage,
        after=project.qpu_seconds,
        threshold=_qpu_seconds_low_threshold,
    )
    if notice_type is not None:
        await _notify_project(database, project, notice_type)
    return project


async def cancel_job(
    database: Database,
    bcc_client: BccClient,
    job_id: UUID,
    user_id: str,
    details: CancellationDetails,
) -> GeneralMessage:
    """Cancels the job in its BCC, then marks it cancelled if the BCC succeeded

    Args:
        database: the database where the jobs are stored
        bcc_client: the client of the BCC running the job
        job_id: the unique identifier of the job
        user_id: the unique identifier of the user cancelling it
        details: the extra information passed when cancelling the job

    Returns:
        the BCC's answer
    """
    response = await bcc_client.cancel_job(job_id, user_id=user_id, body=details)
    if response["status"] == "success":
        await update_job(
            database,
            job_id=str(job_id),
            payload=JobUpdate(
                cancellation_reason=details.reason, status=JobStatus.CANCELLED
            ),
        )

    return response


async def delete_job(
    database: Database,
    bcc_client: BccClient,
    job_id: UUID,
    user_id: str,
) -> GeneralMessage:
    """Deletes the job from its BCC, then from the database if the BCC succeeded

    Args:
        database: the database where the jobs are stored
        bcc_client: the client of the BCC running the job
        job_id: the unique identifier of the job
        user_id: the unique identifier of the user deleting it

    Returns:
        the BCC's answer

    Raises:
        NotFoundError: no matches for {filter}
    """
    response = await bcc_client.delete_job(job_id, user_id=user_id)
    if response["status"] == "success":
        count = await database.delete_many(Job, filter={"job_id": str(job_id)})
        if count == 0:
            raise NotFoundError(f"no matches for { {'job_id': str(job_id)} }")

    return response


async def get_readable_job(
    database: Database,
    job_id: UUID,
    user: User,
    should_decrypt_token: bool = False,
) -> Job:
    """Gets a job the user may read: one they submitted, one with no recorded submitter, or any if they are an admin

    Args:
        database: the database where the jobs are stored
        job_id: the `job_id` of the job to be returned
        user: the user reading the job
        should_decrypt_token: whether to decrypt the returned access token

    Raises:
        utils.exc.NotFoundError: no matches for '{search_filter}', also for a job the user may not read

    Returns:
        the job
    """
    job = await get_job(
        database, job_id=job_id, should_decrypt_token=should_decrypt_token
    )
    if not _is_job_readable_by(job, user):
        raise NotFoundError(f"no matches for '{dict(job_id=str(job_id))}'")
    return job


async def count_job_submitters(
    database: Database,
    start_utc: datetime,
    end_utc: datetime,
    should_count_distinct: bool = True,
) -> int:
    """Counts the users who submitted jobs in [start_utc, end_utc), or their submissions

    Args:
        database: the database where the jobs are stored
        start_utc: the start of the window, inclusive
        end_utc: the end of the window, exclusive
        should_count_distinct: whether to count each submitter once; otherwise every job counts

    Returns:
        the number of submitters, or of submitted jobs
    """
    window_filter = {
        "created_at": {
            "$gte": datetime_to_zulu(start_utc),
            "$lt": datetime_to_zulu(end_utc),
        }
    }
    if not should_count_distinct:
        return await database.count(Job, filter=window_filter)

    submitter_ids = await database.find_distinct(Job, "user_id", filter=window_filter)
    return len([user_id for user_id in submitter_ids if user_id is not None])


async def on_startup(
    private_key: RSAPrivateKey, qpu_seconds_low_threshold: float
) -> None:
    """Gives the jobs service what the app is configured with

    Args:
        private_key: the MSS private key, which decrypts the jobs' access tokens
        qpu_seconds_low_threshold: the QPU seconds below which a project is running low
    """
    global _private_key, _qpu_seconds_low_threshold
    _private_key = private_key
    _qpu_seconds_low_threshold = qpu_seconds_low_threshold


def _choose_qpu_notice(
    before: float, after: float, threshold: float
) -> Optional[NoticeTypeId]:
    """Chooses the notice for a project's QPU seconds going from before to after

    Only crossing zero or the threshold alerts, or every later job would alert again.
    """
    if after <= 0 < before:
        return NoticeTypeId.QPU_SECONDS_DEPLETED
    if after < threshold < before:
        return NoticeTypeId.QPU_SECONDS_LOW
    return None


async def _notify_project(
    database: Database, project: Project, notice_type: NoticeTypeId
) -> None:
    """Tells the members a project is out of QPU time, or its admin that it is running low"""
    if notice_type == NoticeTypeId.QPU_SECONDS_DEPLETED:
        user_ids = project.user_ids
        context = ProjectRequestContext(
            project_id=str(project.id), project_name=project.name
        )
    else:
        user_ids = [project.admin_id]
        context = ProjectRequestContext(
            project_id=str(project.id),
            project_name=project.name,
            seconds=round(project.qpu_seconds),
        )
    await notices.create_system_notice(
        database,
        user_ids=user_ids,
        notice_type=notice_type,
        context=context,
        ref_type=RefType.PROJECT,
        ref_id=project.id,
    )


def _is_job_readable_by(job: Job, user: User) -> bool:
    return job.user_id is None or job.user_id == str(user.id) or user.is_superuser
