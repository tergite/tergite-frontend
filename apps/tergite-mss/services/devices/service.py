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

from typing import Any, Dict, List, Optional, Sequence

from libs.storage import Database
from utils.date_time import get_current_timestamp
from utils.exc import NotFoundError

from .dtos import Device, DeviceQuery, DeviceUpsert


async def find_devices(
    database: Database,
    query: DeviceQuery,
    sort: Sequence[str] = (),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Device]:
    """Gets the devices that match the filter

    Args:
        database: the database where the devices are stored
        query: the values every returned device has; its unset fields match anything
        sort: the fields to sort by; a leading '-' sorts descending
        skip: the number of matched devices to skip
        limit: the most devices to return; None returns all

    Raises:
        ValidationError: final results are not valid Device objects
    """
    return await database.find(
        Device,
        filter=query.model_dump(
            exclude_unset=True, exclude_defaults=True, exclude_none=True
        ),
        sort=sort,
        skip=skip,
        limit=limit,
    )


async def get_device(database: Database, name: str) -> Device:
    """Gets the device of the given name

    Raises:
        ValidationError: if the final result could not be validated as a Device
        NotFoundError: no matches for {name: '<name>'}
    """
    device = await database.get(Device, name)
    if device is None:
        raise NotFoundError(f"no matches for '{ {'name': name} }'")
    return device


async def upsert_device(database: Database, payload: DeviceUpsert) -> Device:
    """Creates a new device or updates it if it exists

    Args:
        database: the database where the devices are stored
        payload: the device

    Returns:
        the new device

    Raises:
        ValidationError: if the final object could not be validated
    """
    timestamp = get_current_timestamp()
    payload.updated_at = timestamp
    return await database.update_one(
        Device,
        filter={"name": payload.name},
        update={
            "$set": payload.model_dump(exclude_none=True),
            "$setOnInsert": {"created_at": timestamp},
        },
        should_upsert=True,
    )


async def patch_device(
    database: Database, name: str, payload: Dict[str, Any]
) -> Device:
    """Patches the data of the device of the given name

    Args:
        database: the database where the devices are stored
        name: the name of the device
        payload: the new data to patch into the device data

    Returns:
        the updated device

    Raises:
        NotFoundError: device {name} not found
        ValidationError: if the final object is not validated
    """
    device = await database.update_one(
        Device,
        filter={"name": name},
        update={"$set": {**payload, "updated_at": get_current_timestamp()}},
    )
    if device is None:
        raise NotFoundError(f"device '{name}' not found")
    return device


async def mark_device_online(database: Database, name: str) -> Device:
    """Marks the device of the given name as online

    Raises:
        NotFoundError: device {name} not found
    """
    return await patch_device(
        database, name=name, payload={"last_online": None, "is_online": True}
    )


async def mark_device_offline(
    database: Database, name: str, last_online: str
) -> Device:
    """Marks the device of the given name as offline since the given time

    Args:
        database: the database where the devices are stored
        name: the name of the device
        last_online: the timestamp when the device was last online

    Raises:
        NotFoundError: device {name} not found
    """
    return await patch_device(
        database, name=name, payload={"last_online": last_online, "is_online": False}
    )


async def disconnect_all(database: Database) -> int:
    """Marks every device offline, returning how many changed"""
    timestamp = get_current_timestamp()
    return await database.update_many(
        Device,
        filter={},
        update={
            "$set": {
                "last_online": timestamp,
                "is_online": False,
                "updated_at": timestamp,
            }
        },
    )
