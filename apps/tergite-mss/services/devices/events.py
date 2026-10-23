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
from typing import Dict

from libs.storage import Database
from services import calibration as calibration_service
from services import jobs as jobs_service
from services.auth import ProjectDatabase
from services.calibration import DeviceCalibration
from services.jobs import JobUpdate
from utils.api import GeneralMessage
from utils.exc import ForbiddenError

from .dtos import DeviceEventHandler, DeviceEventName, DeviceSwitchData, DeviceUpsert
from .service import mark_device_offline, mark_device_online, upsert_device


async def on_job_updated_event(
    device: str,
    data: JobUpdate,
    database: Database,
    project_db: ProjectDatabase,
    **kwargs,
) -> GeneralMessage:
    """Handles the device event of job updated

    This may raise pydantic.error_wrappers.ValidationError in case
    the timestamps have an unexpected structure

    Args:
        device: the name of the device for this job
        data: the new job update
        database: the database where the jobs are stored
        project_db: the database containing the project

    Returns:
        the general message with the updated job

    Raises:
        pydantic.error_wrappers.ValidationError: job with an unexpected structure
    """
    job_id = data.job_id
    old_job = await jobs_service.update_job(database, job_id=job_id, payload=data)

    qpu_usage = getattr(data.timestamps, "resource_usage", None)
    if old_job.duration_in_secs is None and qpu_usage is not None:
        await jobs_service.update_qpu_usage(
            database, project_db=project_db, job_id=job_id, qpu_usage=qpu_usage
        )

    updated_job = await jobs_service.get_job(
        database, job_id=job_id, should_decrypt_token=True
    )
    return {
        "status": "success",
        "data": updated_job.model_dump(mode="json"),
    }


async def on_device_initialized_event(
    device: str, data: DeviceUpsert, database: Database, **kwargs
) -> GeneralMessage:
    """Handles the device event of device initialized

    Args:
        device: the name of the device
        data: the new device parameters
        database: the database where the devices are stored

    Returns:
        the general message with the updated job

    Raises:
        ForbiddenError: editing '{another device}' is not allowed
        ValueError: could not insert '{payload['name']}' document
        ValidationError: if the final object could not be validated
    """
    if data.name != device:
        raise ForbiddenError(f"editing '{data.name}' is not allowed")

    upserted_record = await upsert_device(database, payload=data)
    return {
        "status": "success",
        "data": upserted_record.model_dump(mode="json"),
    }


async def on_device_switched_off_event(
    device: str, data: DeviceSwitchData, database: Database, **kwargs
) -> GeneralMessage:
    """Handles the device event of device switched off event

    Args:
        device: the name of the device
        data: the extra information about the event
        database: the database where the devices are stored

    Returns:
        the general message with the updated job

    Raises:
        NotFoundError: device {device} not found
        ValidationError: if the final object is not validated
    """
    patched_record = await mark_device_offline(
        database, name=device, last_online=data.date.isoformat()
    )
    return {
        "status": "success",
        "data": patched_record.model_dump(mode="json"),
    }


async def on_device_switched_on_event(
    device: str, data: DeviceSwitchData, database: Database, **kwargs
) -> GeneralMessage:
    """Handles the device event of device switched on event

    Args:
        device: the name of the device
        data: the extra information about the event
        database: the database where the devices are stored

    Returns:
        the general message with the updated job

    Raises:
        NotFoundError: device {device} not found
        ValidationError: if the final object is not validated
    """
    patched_record = await mark_device_online(database, name=device)
    return {
        "status": "success",
        "data": patched_record.model_dump(mode="json"),
    }


async def on_device_recalibrated_event(
    device: str, data: DeviceCalibration, database: Database, **kwargs
) -> GeneralMessage:
    """Handles the device event of device recalibrated

    Args:
        device: the name of the device
        data: the new device calibration data
        database: the database where the calibrations are stored

    Returns:
        the general message with the upserted calibration data

    Raises:
        ForbiddenError: editing '{another device}' is not allowed
        ValueError: could not insert '{payload['name']}' document
        ValidationError: if the final object could not be validated
    """
    if data.name != device:
        raise ForbiddenError(f"editing '{data.name}' is not allowed")

    upserted_record = await calibration_service.create_calibration(
        database, record=data
    )
    return {
        "status": "success",
        "data": upserted_record.model_dump(mode="json"),
    }


EVENT_HANDLERS: Dict[DeviceEventName, DeviceEventHandler] = {
    DeviceEventName.INITIALIZED: on_device_initialized_event,
    DeviceEventName.RECALIBRATED: on_device_recalibrated_event,
    DeviceEventName.JOB_UPDATED: on_job_updated_event,
    DeviceEventName.SWITCHED_OFF: on_device_switched_off_event,
    DeviceEventName.SWITCHED_ON: on_device_switched_on_event,
}
"""A map of event handlers for device events"""
