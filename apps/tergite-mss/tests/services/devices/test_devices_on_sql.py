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
"""The devices service on each SQL database: whole-device upserts and status patches"""
import pytest

from libs.storage import Database
from services import devices
from services.devices import DeviceQuery
from services.devices.dtos import DeviceUpsert
from tests._utils.fixtures import load_json_fixture

_DEVICE_LIST = load_json_fixture("device_list.json")


@pytest.fixture
async def database(sql_database_url):
    database = Database(sql_database_url, schemas=devices.SCHEMAS)
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


async def test_devices_are_found_by_query_and_marked_offline(database):
    for payload in _DEVICE_LIST[:3]:
        await devices.upsert_device(database, DeviceUpsert(**payload))
    name = _DEVICE_LIST[0]["name"]

    found = await devices.find_devices(database, DeviceQuery(name=name))
    online = await devices.mark_device_online(database, name)
    count = await devices.disconnect_all(database)

    assert [device.name for device in found] == [name]
    assert online.is_online is True
    assert count == 3
    assert (await devices.get_device(database, name)).is_online is False
