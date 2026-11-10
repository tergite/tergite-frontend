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

from loguru import logger

from libs.storage import Database
from services import calibration as calibration_service
from services import jobs as jobs_service
from services.calibration import DeviceCalibration
from services.jobs import JobUpdate
from utils.api import GeneralMessage
from utils.exc import ForbiddenError, JobAlreadyEndedError

from .dtos import DeviceEventHandler, DeviceEventName, DeviceSwitchData, DeviceUpsert
from .service import switch_off_device, switch_on_device, upsert_device


async def on_job_updated_event(
    device: str,
    data: JobUpdate,
    database: Database,
    **kwargs,
) -> GeneralMessage:
    """Handles the device event of job updated

    This may raise pydantic.error_wrappers.ValidationError in case
    the timestamps have an unexpected structure

    Args:
        device: the name of the device for this job
        data: the new job update
        database: the database where the jobs and projects are stored
        kwargs: any other arguments the event handlers are called with, ignored

    An update that would change the status of a job that has ended is ignored, and the
    job is returned as it is. An update of another device's job is refused.

    Returns:
        the general message with the updated job

    Raises:
        pydantic.error_wrappers.ValidationError: job with an unexpected structure
        ForbiddenError: updating the job of '{job.device}' is not allowed
    """
    job_id = data.job_id
    try:
        old_job = await jobs_service.update_job(
            database, job_id=job_id, payload=data, device=device
        )
    except JobAlreadyEndedError as exp:
        # another ending, crossing this one; a refusal would only be logged
        logger.info(f"ignored the job_updated event of {device}: {exp}")
        old_job = None

    qpu_usage = getattr(data.timestamps, "resource_usage", None)
    if (
        old_job is not None
        and old_job.duration_in_secs is None
        and qpu_usage is not None
    ):
        await jobs_service.update_qpu_usage(
            database, job_id=job_id, qpu_usage=qpu_usage
        )

    updated_job = await jobs_service.get_job(
        database, job_id=job_id, should_decrypt_token=True
    )
    return {
        "status": "success",
        "data": updated_job.model_dump(mode="json", exclude_none=True),
    }


async def on_device_initialized_event(
    device: str, data: DeviceUpsert, database: Database, **kwargs
) -> GeneralMessage:
    """Handles the device event of device initialized

    Args:
        device: the name of the device
        data: the new device parameters
        database: the database where the devices are stored
        kwargs: any other arguments the event handlers are called with, ignored

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
        "data": upserted_record.model_dump(mode="json", exclude_none=True),
    }


async def on_device_switched_off_event(
    device: str, data: DeviceSwitchData, database: Database, **kwargs
) -> GeneralMessage:
    """Handles the device event of device switched off event

    Args:
        device: the name of the device
        data: the extra information about the event
        database: the database where the devices are stored
        kwargs: any other arguments the event handlers are called with, ignored

    Returns:
        the general message with the updated job

    Raises:
        NotFoundError: device {device} not found
        ValidationError: if the final object is not validated
    """
    patched_record = await switch_off_device(database, name=device, date=data.date)
    return {
        "status": "success",
        "data": patched_record.model_dump(mode="json", exclude_none=True),
    }


async def on_device_switched_on_event(
    device: str, data: DeviceSwitchData, database: Database, **kwargs
) -> GeneralMessage:
    """Handles the device event of device switched on event

    Args:
        device: the name of the device
        data: the extra information about the event
        database: the database where the devices are stored
        kwargs: any other arguments the event handlers are called with, ignored

    Returns:
        the general message with the updated job

    Raises:
        NotFoundError: device {device} not found
        ValidationError: if the final object is not validated
    """
    patched_record = await switch_on_device(database, name=device)
    return {
        "status": "success",
        "data": patched_record.model_dump(mode="json", exclude_none=True),
    }


async def on_device_recalibrated_event(
    device: str, data: DeviceCalibration, database: Database, **kwargs
) -> GeneralMessage:
    """Handles the device event of device recalibrated

    Args:
        device: the name of the device
        data: the new device calibration data
        database: the database where the calibrations are stored
        kwargs: any other arguments the event handlers are called with, ignored

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
    return {"status": "success", "data": upserted_record.model_dump(mode="json")}


EVENT_HANDLERS: Dict[DeviceEventName, DeviceEventHandler] = {
    DeviceEventName.INITIALIZED: on_device_initialized_event,
    DeviceEventName.RECALIBRATED: on_device_recalibrated_event,
    DeviceEventName.JOB_UPDATED: on_job_updated_event,
    DeviceEventName.SWITCHED_OFF: on_device_switched_off_event,
    DeviceEventName.SWITCHED_ON: on_device_switched_on_event,
}
"""A map of event handlers for device events"""
