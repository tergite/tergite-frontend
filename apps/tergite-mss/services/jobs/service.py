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
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple, cast
from uuid import UUID

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

import settings
from services import notices
from services.external.bcc import BccClient, CancellationDetails
from settings import PRIVATE_KEY_FILE
from utils import mongodb as mongodb_utils
from utils.api import GeneralMessage
from utils.crypto import decrypt_message
from utils.date_time import datetime_to_zulu
from utils.exc import NotFoundError

from ..auth import Project, User
from ..notices import NoticeType
from ..notices.dtos import ProjectRequestContext, RefType
from .dtos import CreatedJobResponse, Job, JobCreate, JobStatus, JobUpdate

if TYPE_CHECKING:
    from ..auth.projects.database import ProjectDatabase


# FIXME: Add init_strict_beanie and an on_startup function


async def get_job(
    db: AsyncIOMotorDatabase,
    job_id: UUID,
    should_decrypt_token: bool = False,
    private_key_file: Path = PRIVATE_KEY_FILE,
    key_password: Optional[bytes] = settings.CONFIG.private_key_password,
) -> Job:
    """Gets a job by job_id

    Args:
        db: the mongo database from where to get the job
        job_id: the `job_id` of the job to be returned
        should_decrypt_token: whether to decrypt the returned access token
        private_key_file: the path to the private key
        key_password: the password to decrypt the private key PEM file

    Raises:
        utils.exc.NotFoundError: no matches for '{search_filter}'.
        ValidationError: the document does not satisfy the schema passed

    Returns:
        the job as a dict
    """
    result = await mongodb_utils.find_one(
        db.jobs, {"job_id": str(job_id)}, schema=Job, dropped_fields=("_id",)
    )
    if should_decrypt_token and result.access_token:
        result.access_token = decrypt_message(
            private_key_file=private_key_file,
            msg=result.access_token,
            password=key_password,
        )

    return result


async def create_job(
    db: AsyncIOMotorDatabase,
    bcc_client: BccClient,
    payload: JobCreate,
    project_id: Optional[str],
    user_id: Optional[str],
    request_id: str,
) -> CreatedJobResponse:
    """Creates a new job for the given backend

    Args:
        db: the mongo database from where to create the job
        bcc_client: the HTTP client for accessing BCC
        payload: the job to create
        project_id: the unique identifier of the project the job is billed to
        user_id: the unique identifier of the user
        request_id: the unique identifier of the current request

    Returns:
        the created job details

    Raises:
            ValueError: job id '{job_id}' already exists
                See :meth:`utils.http_clients.BccClient.save_credentials`
            ServiceUnavailableError: device is currently unavailable.
                See :meth:`utils.http_clients.BccClient.save_credentials`
    """
    job = Job(**payload.model_dump(), project_id=project_id, user_id=user_id)
    logger.info(f"Creating new job with id: {job.job_id} for user: {user_id}")
    encrypted_token, token = await bcc_client.get_token(
        job_id=job.job_id, user_id=user_id, request_id=request_id
    )
    job.access_token = encrypted_token
    await mongodb_utils.insert_one(collection=db.jobs, document=job.model_dump())
    logger.debug(f"Job {job.job_id} successfully saved to database")

    upload_url = _without_special_docker_host_domain(
        f"{bcc_client.public_base_url}/jobs"
    )

    return {
        "job_id": job.job_id,
        "upload_url": upload_url,
        "access_token": token,
    }


async def get_latest_many(
    db: AsyncIOMotorDatabase,
    filters: Optional[dict] = None,
    limit: Optional[int] = None,
    skip: int = 0,
    exclude: Tuple[str] = ("access_token",),
    sort: List[str] = (),
) -> List[Job]:
    """Retrieves the latest jobs up to the given limit

    By default, the access_token is not returned when many jobs are requested for.
    This is because such requests are usually not to submit the job but rather to view it.

    Args:
        db: the mongo database from where to get the jobs
        filters: the mongodb like filters which all returned records should satisfy
        limit: maximum number of records to return; default = None meaning all of them
        skip: the number of records to skip; default = 0
        exclude: the fields to exclude
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ()
    """
    results = await mongodb_utils.find(
        db.jobs,
        filters=filters,
        exclude=exclude,
        limit=limit,
        skip=skip,
        sort=sort,
        schema=Job,
        skip_validation=True,
    )
    # just for the
    results = cast(list[Job], results)
    return results


async def update_job(db: AsyncIOMotorDatabase, job_id: str, payload: JobUpdate) -> Job:
    """Updates the job of the given job_id

    Args:
        db: the mongo database from where to get the job
        job_id: the job id of the job
        payload: the new payload to update in job

    Returns:
        the job before it was modified

    Raises:
        NotFoundError: no documents matching {"job_id": job_id} were found
    """
    document = await mongodb_utils.update_one(
        db.jobs,
        _filter={"job_id": job_id},
        payload=payload.model_dump(),
        return_document=ReturnDocument.BEFORE,
    )
    return Job.model_validate(document)


async def update_qpu_usage(
    db: AsyncIOMotorDatabase,
    project_db: "ProjectDatabase",
    job_id: UUID,
    qpu_usage: float,
    qpu_threshold: float = settings.CONFIG.projects.qpu_seconds_low_threshold,
) -> Optional[Project]:
    """Updates the resource usage for the job of the given job_id

    Args:
        db: the mongo database from where to get the job
        project_db: the ProjectDatabase instance where projects are found
        job_id: the job id of the job
        qpu_usage: the resource usage in seconds
        qpu_threshold: the project qpu threshold below which a project is seen as running out

    Return:
        the updated project if the job was attached to a project, else None

    Raises:
        utils.exc.NotFoundError: no matches for '{"job_id": job_id}'.
        utils.exc.NotFoundError: project '{project_id}' for job '{job_id}' not found
        KeyError: 'project_id'
    """
    job = await get_job(db, job_id=job_id)
    project_id = job.project_id
    project = await project_db.increment_qpu_seconds(
        project_id=project_id, qpu_seconds=-qpu_usage
    )
    if project is None:
        if project_id is not None:
            raise NotFoundError(f"project '{project_id}' for job '{job_id}' not found")
        return project

    # alert only on crossing the threshold or zero, or every later job would alert again
    qpu_seconds_before = project.qpu_seconds + qpu_usage
    was_above_threshold = qpu_seconds_before > qpu_threshold
    is_running_low = project.qpu_seconds < qpu_threshold
    is_depleted = project.qpu_seconds <= 0 < qpu_seconds_before

    if is_depleted:
        await notices.create_system_notice(
            user_ids=project.user_ids,
            notice_type=NoticeType.QPU_SECONDS_DEPLETED.id,
            context=ProjectRequestContext(
                project_id=str(project.id), project_name=project.name
            ),
            ref_type=RefType.PROJECT,
            ref_id=project.id,
        )

    elif is_running_low and was_above_threshold:
        await notices.create_system_notice(
            user_ids=[project.admin_id],
            notice_type=NoticeType.QPU_SECONDS_LOW.id,
            context=ProjectRequestContext(
                project_id=str(project.id),
                project_name=project.name,
                seconds=round(project.qpu_seconds),
            ),
            ref_type=RefType.PROJECT,
            ref_id=project.id,
        )

    return project


async def cancel_job(
    db: AsyncIOMotorDatabase,
    bcc_client: BccClient,
    job_id: UUID,
    user_id: str,
    request_id: str,
    details: CancellationDetails,
) -> GeneralMessage:
    """Cancels the job in its BCC, then marks it cancelled if the BCC succeeded

    Args:
        db: the database where the jobs are stored
        bcc_client: the client of the BCC running the job
        job_id: the unique identifier of the job
        user_id: the unique identifier of the user cancelling it
        request_id: the unique identifier of the current request
        details: the extra information passed when cancelling the job

    Returns:
        the BCC's answer
    """
    response = await bcc_client.cancel_job(
        job_id, user_id=user_id, request_id=request_id, body=details
    )
    if response["status"] == "success":
        await update_job(
            db,
            job_id=str(job_id),
            payload=JobUpdate(
                cancellation_reason=details.reason, status=JobStatus.CANCELLED
            ),
        )

    return response


async def delete_job(
    db: AsyncIOMotorDatabase,
    bcc_client: BccClient,
    job_id: UUID,
    user_id: str,
    request_id: str,
) -> GeneralMessage:
    """Deletes the job from its BCC, then from the database if the BCC succeeded

    Args:
        db: the database where the jobs are stored
        bcc_client: the client of the BCC running the job
        job_id: the unique identifier of the job
        user_id: the unique identifier of the user deleting it
        request_id: the unique identifier of the current request

    Returns:
        the BCC's answer

    Raises:
        DatabaseError: server failed deleting documents
        NotFoundError: no matches for {filter}
    """
    response = await bcc_client.delete_job(
        job_id, user_id=user_id, request_id=request_id
    )
    if response["status"] == "success":
        await mongodb_utils.delete_many(db.jobs, _filter={"job_id": str(job_id)})

    return response


async def get_readable_job(
    db: AsyncIOMotorDatabase,
    job_id: UUID,
    user: User,
    should_decrypt_token: bool = False,
) -> Job:
    """Gets a job the user may read: one they submitted, one with no recorded submitter, or any if they are an admin

    Args:
        db: the mongo database from where to get the job
        job_id: the `job_id` of the job to be returned
        user: the user reading the job
        should_decrypt_token: whether to decrypt the returned access token

    Raises:
        utils.exc.NotFoundError: no matches for '{search_filter}', also for a job the user may not read

    Returns:
        the job
    """
    job = await get_job(db, job_id=job_id, should_decrypt_token=should_decrypt_token)
    if not _is_job_readable_by(job, user):
        raise NotFoundError(f"no matches for '{dict(job_id=str(job_id))}'")
    return job


async def count_job_submitters(
    db: AsyncIOMotorDatabase,
    start_utc: datetime,
    end_utc: datetime,
    should_count_distinct: bool = True,
) -> int:
    """Counts the users who submitted jobs in [start_utc, end_utc), or their submissions

    Args:
        db: the mongo database holding the jobs
        start_utc: the start of the window, inclusive
        end_utc: the end of the window, exclusive
        should_count_distinct: whether to count each submitter once; otherwise every job counts

    Returns:
        the number of submitters, or of submitted jobs
    """
    window = {
        "created_at": {
            "$gte": datetime_to_zulu(start_utc),
            "$lt": datetime_to_zulu(end_utc),
        }
    }
    if not should_count_distinct:
        return await db.jobs.count_documents(window)

    submitter_ids = await db.jobs.distinct("user_id", window)
    return len([user_id for user_id in submitter_ids if user_id is not None])


def build_readable_jobs_filter(filters: dict, user: User) -> dict:
    """Narrows a jobs filter to the jobs the user may read"""
    if user.is_superuser:
        return filters
    return {"$and": [filters, {"user_id": {"$in": [user.id, None]}}]}


def _is_job_readable_by(job: Job, user: User) -> bool:
    return job.user_id is None or job.user_id == user.id or user.is_superuser


def _without_special_docker_host_domain(url: str) -> str:
    """Removes the docker host's URL special domain 'host.docker.internal'

    This is useful when the url is to be used by an application outside
    the docker instance on which this frontend is running

    Args:
        url: the URL that might contain the docker host's special domain

    Returns:
        the URL updated with the special 'host.docker.internal' removed
    """
    return url.replace("host.docker.internal", "127.0.0.1")
