# This code is part of Tergite
#
# (C) Copyright Simon Genne, Arvid Holmqvist, Bashar Oumari, Jakob Ristner,
#               Björn Rosengren, and Jakob Wik 2022 (BSc project)
# (C) Copyright Abdullah-Al Amin 2022
# (C) Copyright Martin Ahindura 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import Any, Dict, List, Optional

import pymongo
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils import mongodb as mongodb_utils
from utils.date_time import get_current_timestamp
from utils.exc import NotFoundError

from .dtos import Device, DeviceUpsert


async def get_all_devices(
    db: AsyncIOMotorDatabase,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    skip: int = 0,
    sort: List[str] = (),
) -> List[Device]:
    """Gets all devices in the devices collection

    Args:
        db: the mongo database from which to get the databases
        filters: the mongodb-like filters to use to extract the devices
        limit: the number of results to return: default = None meaning all of them
        skip: the number of records to skip; default = 0
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ()

    Returns:
        a list of all devices found in the devices collection

    Raises:
        ValidationError: final results are not valid Device objects
    """
    return await mongodb_utils.find(
        db.devices, filters=filters, limit=limit, skip=skip, sort=sort, schema=Device
    )


async def get_one_device(db: AsyncIOMotorDatabase, name: str) -> Device:
    """Gets the device of the given name

    Args:
        db: the mongo database where the device information is stored
        name: the name of the device to return

    Returns:
        the device as a dictionary

    Raises:
        ValidationError: if the final result could not be validated as a Device
        NotFoundError: no matches for {name: '<name>'}
    """
    return await mongodb_utils.find_one(db.devices, {"name": name}, schema=Device)


async def upsert_device(db: AsyncIOMotorDatabase, payload: DeviceUpsert) -> Device:
    """Creates a new device or updates it if it exists

    Args:
        db: the mongo database where the device information is stored
        payload: the device

    Returns:
        the new device

    Raises:
        ValueError: could not insert '{payload['name']}' document
        ValidationError: if the final object could not be validated
    """
    timestamp = get_current_timestamp()
    payload.updated_at = timestamp

    device = await db.devices.find_one_and_update(
        {"name": payload.name},
        {"$set": payload.model_dump(), "$setOnInsert": {"created_at": timestamp}},
        upsert=True,
        return_document=pymongo.ReturnDocument.AFTER,
    )

    if device is None:
        raise ValueError(
            f"could not insert '{payload.name}' document.",
        )

    return Device.model_validate(device)


async def patch_device(
    db: AsyncIOMotorDatabase, name: str, payload: Dict[str, Any]
) -> Device:
    """Patches the devices data for the device of the given name

    Args:
        db: the mongo database from where to get the job
        name: the name of the device
        payload: the new data to patch into the device data

    Returns:
        the number of documents that were modified

    Raises:
        ValueError: server failed updating documents
        NotFoundError: device {name} not found
        ValidationError: if the final object is not validated
    """
    device = await db.devices.find_one_and_update(
        {"name": name},
        {"$set": {**payload, "updated_at": get_current_timestamp()}},
        return_document=pymongo.ReturnDocument.AFTER,
    )

    if device is None:
        raise NotFoundError(f"device '{name}' not found")

    return Device.model_validate(device)


async def connect_device(db: AsyncIOMotorDatabase, name: str):
    """Connects the given device to this API

    Args:
        db: the mongo database where the device data is stored
        name: the name of the device

    Returns:
        the updated device
    """
    return await patch_device(
        db, name=name, payload={"last_online": None, "is_online": True}
    )


async def disconnect_device(db: AsyncIOMotorDatabase, name: str):
    """Disconnects the given device to this API

    Args:
        db: the mongo database where the device data is stored
        name: the name of the device

    Returns:
        the updated device
    """
    return await patch_device(
        db,
        name=name,
        payload={"last_online": get_current_timestamp(), "is_online": False},
    )


async def disconnect_all(db: AsyncIOMotorDatabase):
    """Disconnects all connected devices

    Args:
        db: the mongo database where to register the device

    Returns:
        the number of updated records
    """
    result = await db.devices.update_many(
        {},
        {
            "$set": {
                "last_online": get_current_timestamp(),
                "is_online": False,
                "updated_at": get_current_timestamp(),
            }
        },
    )
    return result.modified_count
