# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Module containing event handlers"""
from motor.motor_asyncio import AsyncIOMotorDatabase

import settings
from services import calibration as calibration_service
from services import devices as devices_service
from services import jobs as jobs_service
from services.auth import ProjectDatabase
from services.calibration import DeviceCalibration
from services.devices import DeviceUpsert
from services.external import puhuri as puhuri_service
from services.jobs import JobUpdate
from utils.api import GeneralMessage


async def on_job_updated_event(
    device: str,
    data: JobUpdate,
    db: AsyncIOMotorDatabase,
    project_db: ProjectDatabase,
    **kwargs,
) -> GeneralMessage:
    """Handles the device event of job updated

    This may raise pydantic.error_wrappers.ValidationError in case
    the timestamps have an unexpected structure

    Args:
        device: the name of the device for this job
        data: the new job update
        db: the mongo db instance where job data is stored
        project_db: the database containing the project

    Returns:
        the general message with the updated job

    Raises:
        pydantic.error_wrappers.ValidationError: job with an unexpected structure
    """
    job_id = data.job_id
    old_job = await jobs_service.update_job(db, job_id=job_id, payload=data)

    qpu_usage = getattr(data.timestamps, "resource_usage", None)
    if old_job.duration_in_secs is None and qpu_usage is not None:
        project = await jobs_service.update_qpu_usage(
            db, project_db=project_db, job_id=job_id, qpu_usage=qpu_usage
        )

        if settings.CONFIG.puhuri.is_enabled:
            await puhuri_service.save_qpu_usage(
                db, job_id=job_id, project=project, qpu_usage=qpu_usage
            )
    updated_job = await jobs_service.get_one(db, job_id=job_id, is_token_decrypted=True)
    return {
        "status": "success",
        "data": updated_job.model_dump(mode="json"),
    }


async def on_device_initialized_event(
    device: str, data: DeviceUpsert, db: AsyncIOMotorDatabase, **kwargs
) -> GeneralMessage:
    """Handles the device event of device initialized

    Args:
        device: the name of the device
        data: the new device parameters
        db: the mongo db instance where device data is stored

    Returns:
        the general message with the updated job

    Raises:
        PermissionError: editing '{another device}' is not allowed
        ValueError: could not insert '{payload['name']}' document
        ValidationError: if the final object could not be validated
    """
    if data.name != device:
        raise PermissionError(f"editing '{data.name}' is not allowed")

    upserted_record = await devices_service.upsert_device(db, payload=data)
    return {
        "status": "success",
        "data": upserted_record.model_dump(mode="json"),
    }


async def on_device_recalibrated_event(
    device: str, data: DeviceCalibration, db: AsyncIOMotorDatabase, **kwargs
) -> GeneralMessage:
    """Handles the device event of device recalibrated

    Args:
        device: the name of the device
        data: the new device calibration data
        db: the mongo db instance where the calibration data is stored

    Returns:
        the general message with the upserted calibration data

    Raises:
        PermissionError: editing '{another device}' is not allowed
        ValueError: could not insert '{payload['name']}' document
        ValidationError: if the final object could not be validated
    """
    if data.name != device:
        raise PermissionError(f"editing '{data.name}' is not allowed")

    upserted_record = await calibration_service.insert_one(db, record=data)
    return {
        "status": "success",
        "data": upserted_record.model_dump(mode="json"),
    }
