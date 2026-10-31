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

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from libs.storage import Database
from utils.date_time import get_current_timestamp
from utils.exc import NotFoundError

from .dtos import (
    Device,
    DeviceConnection,
    DeviceQuery,
    DeviceUpsert,
    SwitchedOffDevice,
)

# how long a connection counts unless the MSS process holding it refreshes it, which it does
# every CONNECTION_REFRESH_SECONDS; past it, the process is taken to have died with it
CONNECTION_TTL_SECONDS = 90.0
CONNECTION_REFRESH_SECONDS = 30.0


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

    Returns:
        the matching devices

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

    Args:
        database: the database where the devices are stored
        name: the name of the device

    Returns:
        the device

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
    await database.update_one(
        Device,
        filter={"name": payload.name},
        update={
            "$set": payload.model_dump(exclude_none=True),
            "$setOnInsert": {"created_at": timestamp},
        },
        should_upsert=True,
    )
    # the payload's is_online is the backend's view; MSS's is its connections'
    await sync_online_flags(database, names=[payload.name])
    return await get_device(database, payload.name)


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


async def add_connection(
    database: Database, device_name: str, ttl: float = CONNECTION_TTL_SECONDS
) -> str:
    """Records a websocket of the device's backend, which marks the device online unless it
    is switched off

    Args:
        database: the database where the devices are stored
        device_name: the name of the device
        ttl: the seconds the connection counts before it lapses, unless refreshed

    Returns:
        the connection's id
    """
    connection = await database.insert(
        DeviceConnection,
        DeviceConnection(device_name=device_name, expires_at=_get_expiry(ttl)),
    )
    await sync_online_flags(database, names=[device_name])
    return connection.id


async def remove_connection(database: Database, connection_id: str) -> None:
    """Forgets the websocket, which marks its device offline if it was the last

    Args:
        database: the database where the devices are stored
        connection_id: the id of the websocket's connection
    """
    connection = await database.delete_one(
        DeviceConnection, filter={"id": connection_id}
    )
    if connection is not None:
        await sync_online_flags(database, names=[connection.device_name])


async def keep_connections_live(
    database: Database,
    connection_ids: Sequence[str],
    ttl: float = CONNECTION_TTL_SECONDS,
) -> None:
    """Keeps the websockets from lapsing for another ttl seconds

    Args:
        database: the database where the connections are stored
        connection_ids: the ids of the websockets' connections
        ttl: the seconds the connections count for from now
    """
    if connection_ids:
        await database.update_many(
            DeviceConnection,
            filter={"id": {"$in": list(connection_ids)}},
            update={"$set": {"expires_at": _get_expiry(ttl)}},
        )


async def sync_online_flags(
    database: Database, names: Optional[Sequence[str]] = None
) -> None:
    """Marks each device, or the named ones, online if it has a live connection and is not
    switched off, and offline otherwise, since now

    Args:
        database: the database where the devices and connections are stored
        names: the names of the devices to mark; None marks every device
    """
    device_filter = {} if names is None else {"name": {"$in": list(names)}}
    connected_names = set(
        await database.find_distinct(DeviceConnection, "device_name", filter={})
    )
    switched_off_names = set(
        await database.find_distinct(SwitchedOffDevice, "name", filter={})
    )
    for device in await database.find(Device, filter=device_filter):
        is_online = (
            device.name in connected_names and device.name not in switched_off_names
        )
        if is_online != device.is_online:
            last_online = None if is_online else get_current_timestamp()
            await patch_device(
                database,
                name=device.name,
                payload={"is_online": is_online, "last_online": last_online},
            )


async def switch_off_device(database: Database, name: str, date: datetime) -> Device:
    """Marks the device switched off, and so offline since the date, until switched on

    Args:
        database: the database where the devices are stored
        name: the name of the device
        date: when the device was switched off

    Returns:
        the updated device

    Raises:
        NotFoundError: device {name} not found
    """
    await get_device(database, name)
    await database.update_one(
        SwitchedOffDevice,
        filter={"name": name},
        update={"$set": {"name": name, "switched_off_at": date}},
        should_upsert=True,
    )
    return await patch_device(
        database,
        name=name,
        payload={"is_online": False, "last_online": date.isoformat()},
    )


async def switch_on_device(database: Database, name: str) -> Device:
    """Marks the device switched on, and so online again if connected

    Args:
        database: the database where the devices are stored
        name: the name of the device

    Returns:
        the updated device

    Raises:
        NotFoundError: device {name} not found
    """
    await database.delete_one(SwitchedOffDevice, filter={"name": name})
    await sync_online_flags(database, names=[name])
    return await get_device(database, name)


def _get_expiry(ttl: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=ttl)
