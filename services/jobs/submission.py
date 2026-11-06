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

MSS checks the circuits, creates the job as for the SDK, and uploads the job file to the
backend itself, so a browser never talks to a backend.
"""

from typing import List, Optional

from loguru import logger

from libs.qasm import QasmError, read_circuit
from libs.storage import Database
from services.external.bcc import BccClient
from utils.date_time import get_current_timestamp
from utils.exc import BccHttpError, InvalidInputError, ServiceUnavailableError

from ..auth import (
    STRICT,
    Project,
    TokenOwner,
    User,
    check_project_access,
    get_project_if_member,
)
from .dtos import Job, JobCreate, JobFile, JobSource, JobStatus, JobSubmission
from .service import create_job, get_job

# the submission's fields that are the job's source, without where it runs or who pays
SOURCE_FIELDS = set(JobSource.model_fields)


class InvalidCircuitError(InvalidInputError):
    """A submitted circuit that the device cannot run, and where in it the problem is

    Attributes:
        index: the circuit's place in the submission
        message: what is wrong, as a sentence
        line: the line, from 1, if known
        column: the column, from 1, if known
    """

    def __init__(
        self,
        index: int,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
    ):
        super().__init__(message)
        self.index = index
        self.message = message
        self.line = line
        self.column = column


async def submit_job(
    database: Database,
    bcc_client: BccClient,
    submission: JobSubmission,
    user: User,
    number_of_qubits: int,
    calibration_date: str,
) -> Job:
    """Checks the submitted circuits, creates their job and uploads it to the backend

    Args:
        database: the database where the jobs and projects are stored
        bcc_client: the client of the backend of the submission's device
        submission: the circuits, their settings, the device and the project
        user: the user submitting
        number_of_qubits: the device's qubits
        calibration_date: when the device was last calibrated

    Returns:
        the job, pending, or failed with the backend's reason if it refused the file

    Raises:
        UnauthorizedError: the project is inactive, or the user is not its member
        ForbiddenError: the project has no QPU seconds left
        InvalidCircuitError: a circuit the device cannot run
        ServiceUnavailableError: the device is unavailable
        BccHttpError: the backend refused the job file
    """
    project = await _get_project_with_qpu(database, submission.project_id, user)
    num_clbits = _read_circuits(submission, project, number_of_qubits)

    created = await create_job(
        database,
        bcc_client=bcc_client,
        payload=JobCreate(device=submission.device, calibration_date=calibration_date),
        project_id=project.id,
        user_id=str(user.id),
    )
    job_id = created["job_id"]
    source = JobSource.model_validate(submission.model_dump(include=SOURCE_FIELDS))
    await database.update_one(
        Job, {"job_id": job_id}, {"$set": {"source": source.model_dump()}}
    )

    job_file = JobFile.from_source(job_id, source, num_clbits)
    try:
        await bcc_client.upload_job(
            job_id, job_file.model_dump_json(), token=created["access_token"]
        )
    except (BccHttpError, ServiceUnavailableError) as exp:
        await _mark_failed(database, job_id, reason=f"{exp}")
        raise
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


def _read_circuits(
    submission: JobSubmission, project: Project, number_of_qubits: int
) -> List[int]:
    """The classical bits each circuit declares, once each is one the device can run"""
    num_clbits = []
    for index, circuit in enumerate(submission.circuits):
        try:
            info = read_circuit(circuit.qasm)
        except QasmError as exp:
            raise InvalidCircuitError(index, exp.message, exp.line, exp.column)
        if info.num_qubits > number_of_qubits:
            raise InvalidCircuitError(
                index,
                f"the circuit uses {info.num_qubits} qubits, but {submission.device} "
                f"has {number_of_qubits}",
            )
        if info.is_pulse_level and not project.is_pulse_allowed:
            raise InvalidCircuitError(
                index,
                f"project {project.name} may not send pulse-level programs; "
                "an admin can allow it",
            )
        num_clbits.append(info.num_clbits)
    return num_clbits


async def _mark_failed(database: Database, job_id: str, reason: str) -> None:
    """Marks the job failed, for a file the backend never took"""
    await database.update_one(
        Job,
        {"job_id": job_id},
        {
            "$set": {
                "status": JobStatus.FAILED,
                "failure_reason": reason,
                "updated_at": get_current_timestamp(),
            }
        },
    )
