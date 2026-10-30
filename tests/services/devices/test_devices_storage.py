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
"""The devices service on each database: whole-device upserts and status patches"""
import asyncio
from datetime import datetime, timezone

import pytest

from libs.storage import Database
from services import devices
from services.devices import DeviceQuery
from services.devices.dtos import DeviceUpsert
from tests._utils.fixtures import load_json_fixture

_DEVICE_LIST = load_json_fixture("device_list.json")


@pytest.fixture
async def database(database_url):
    database = Database(database_url, schemas=devices.SCHEMAS)
    await database.setup()
    yield database
    await database.close()


async def test_a_device_is_upserted_whole_and_found_by_name(database):
    payload = _DEVICE_LIST[0]

    created = await devices.upsert_device(database, DeviceUpsert(**payload))
    updated = await devices.upsert_device(
        database, DeviceUpsert(**{**payload, "version": "2099.01.0"})
    )

    assert updated.created_at == created.created_at
    assert updated.version == "2099.01.0"
    assert updated.coupling_map == created.coupling_map
    assert await devices.get_device(database, payload["name"]) == updated


async def test_devices_are_found_by_query(database):
    for payload in _DEVICE_LIST[:3]:
        await devices.upsert_device(database, DeviceUpsert(**payload))
    name = _DEVICE_LIST[0]["name"]

    found = await devices.find_devices(database, DeviceQuery(name=name))

    assert [device.name for device in found] == [name]


async def test_a_device_is_online_while_any_process_holds_a_connection(database):
    """A backend opens a websocket per process, possibly to different MSS processes"""
    name = await _upsert_device(database)
    first = await devices.add_connection(database, name)
    second = await devices.add_connection(database, name)

    await devices.remove_connection(database, first)
    with_one = await devices.get_device(database, name)
    await devices.remove_connection(database, second)
    with_none = await devices.get_device(database, name)

    assert (with_one.is_online, with_none.is_online) == (True, False)
    assert with_none.last_online is not None


async def test_connections_left_by_a_dead_process_lapse_and_the_sync_marks_offline(
    database,
):
    name = await _upsert_device(database)
    await devices.add_connection(database, name, ttl=-1)

    await devices.sync_online_flags(database)

    assert (await devices.get_device(database, name)).is_online is False


async def test_connections_refreshed_in_time_keep_the_device_online(database):
    name = await _upsert_device(database)
    connection_id = await devices.add_connection(database, name, ttl=1)
    await asyncio.sleep(0.5)
    await devices.keep_connections_live(database, [connection_id], ttl=60)
    await asyncio.sleep(0.7)

    await devices.sync_online_flags(database)

    assert (await devices.get_device(database, name)).is_online is True


async def test_a_switched_off_device_stays_offline_until_switched_on(database):
    name = await _upsert_device(database)
    await devices.add_connection(database, name)

    switched_off = await devices.switch_off_device(
        database, name, date=datetime.now(timezone.utc)
    )
    await devices.add_connection(database, name)
    connected_again = await devices.get_device(database, name)
    switched_on = await devices.switch_on_device(database, name)

    assert [
        switched_off.is_online,
        connected_again.is_online,
        switched_on.is_online,
    ] == [
        False,
        False,
        True,
    ]


async def test_an_upsert_leaves_the_online_flag_to_the_connections(database):
    """A backend's initialized event carries an is_online of its own, which is not MSS's"""
    name = await _upsert_device(database)
    await devices.add_connection(database, name)

    upserted = await devices.upsert_device(
        database, DeviceUpsert(**{**_DEVICE_LIST[0], "is_online": False})
    )

    assert upserted.is_online is True


async def _upsert_device(database) -> str:
    await devices.upsert_device(database, DeviceUpsert(**_DEVICE_LIST[0]))
    return _DEVICE_LIST[0]["name"]
