# This code is part of Tergite
#
# (C) Copyright Miroslav Dobsicek 2020
# (C) Copyright Simon Genne, Arvid Holmqvist, Bashar Oumari, Jakob Ristner,
#               Björn Rosengren, and Jakob Wik 2022 (BSc project)
# (C) Copyright Fabian Forslund, Niklas Botö 2022
# (C) Copyright Abdullah-Al Amin 2022
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
#
# Refactored by Martin Ahindura on 2023-11-08
"""Service that handles calibration functionality"""
from typing import List, Sequence

from libs.storage import ALL, And, Database, Eq, Filter, Page, Set, SetOnInsert, Sort
from utils.date_time import get_current_timestamp
from utils.exc import NotFoundError

from .dtos import (
    DeviceCalibration,
    DeviceCalibrationCreate,
    DeviceCalibrationLog,
    DeviceCalibrationQuery,
)


async def create_calibration(
    database: Database, record: DeviceCalibrationCreate
) -> DeviceCalibration:
    """Makes the calibration its device's current one, and logs it once

    Args:
        database: the database where the calibrations are stored
        record: the calibration results

    Returns:
        the device's current calibration
    """
    fields = record.model_dump()
    # setting only on insert makes logging the same calibration twice a no-op
    await database.update_one(
        DeviceCalibrationLog,
        where=And(
            Eq("name", record.name), Eq("last_calibrated", record.last_calibrated)
        ),
        changes=[SetOnInsert(field, value) for field, value in fields.items()],
        should_upsert=True,
    )
    return await database.update_one(
        DeviceCalibration,
        where=Eq("name", record.name),
        changes=[
            *(Set(field, value) for field, value in fields.items()),
            Set("updated_at", get_current_timestamp()),
        ],
        should_upsert=True,
    )


async def find_latest_calibrations(
    database: Database,
    where: Filter = ALL,
    sort: Sequence[Sort] = (),
    page: Page = Page(),
) -> List[DeviceCalibration]:
    """Gets the current calibration of every device that matches the filter

    Args:
        database: the database where the calibrations are stored
        where: the filter every returned calibration matches
        sort: the order of the calibrations
        page: which slice of the matched calibrations to return
    """
    return await database.find(DeviceCalibration, where=where, sort=sort, page=page)


async def get_one(database: Database, name: str) -> DeviceCalibration:
    """Gets the current calibration of the given device

    Raises:
        NotFoundError: no matches for {'name': name}
    """
    calibration = await database.get(DeviceCalibration, name)
    if calibration is None:
        raise NotFoundError(f"no matches for '{ {'name': name} }'")
    return calibration


def build_filter(query: DeviceCalibrationQuery) -> Filter:
    """Turns the query's set fields into a filter matching each of them"""
    return And(*(Eq(field, value) for field, value in query.model_dump().items()))
