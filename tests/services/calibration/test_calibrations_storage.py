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
"""The calibration service on each database: the current calibration and its log"""

import pytest

from libs.storage import Database
from services import calibration
from services.calibration import DeviceCalibrationLog
from services.calibration.dtos import DeviceCalibrationCreate, DeviceCalibrationQuery
from tests._utils.fixtures import load_json_fixture

_CALIBRATIONS = load_json_fixture("calibrations.json")


@pytest.fixture
async def database(database_url):
    database = Database(database_url, schemas=calibration.SCHEMAS)
    await database.setup()
    yield database
    await database.close()


async def test_a_calibration_becomes_current_and_is_logged_once(database):
    payload = DeviceCalibrationCreate(**_CALIBRATIONS[0])

    first = await calibration.create_calibration(database, payload)
    again = await calibration.create_calibration(database, payload)

    assert first.qubits == again.qubits
    assert await calibration.get_one(database, payload.name) == again
    assert await database.count(DeviceCalibrationLog) == 1


async def test_the_latest_calibrations_are_found_by_query(database):
    for payload in _CALIBRATIONS:
        await calibration.create_calibration(
            database, DeviceCalibrationCreate(**payload)
        )
    name = _CALIBRATIONS[0]["name"]

    found = await calibration.find_latest_calibrations(
        database, DeviceCalibrationQuery(name=name), sort=["-last_calibrated"]
    )

    assert [item.name for item in found] == [name]
