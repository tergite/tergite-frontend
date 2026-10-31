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
from typing import List, Optional, Sequence

from libs.storage import Database
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
        filter={"name": record.name, "last_calibrated": record.last_calibrated},
        update={"$setOnInsert": fields},
        should_upsert=True,
    )
    return await database.update_one(
        DeviceCalibration,
        filter={"name": record.name},
        update={"$set": {**fields, "updated_at": get_current_timestamp()}},
        should_upsert=True,
    )


async def find_latest_calibrations(
    database: Database,
    query: DeviceCalibrationQuery,
    sort: Sequence[str] = (),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[DeviceCalibration]:
    """Gets the current calibration of every device that matches the filter

    Args:
        database: the database where the calibrations are stored
        query: the values every returned calibration has; its unset fields match anything
        sort: the fields to sort by; a leading '-' sorts descending
        skip: the number of matched calibrations to skip
        limit: the most calibrations to return; None returns all
    """
    return await database.find(
        DeviceCalibration,
        filter=query.model_dump(
            exclude_unset=True, exclude_defaults=True, exclude_none=True
        ),
        sort=sort,
        skip=skip,
        limit=limit,
    )


async def get_one(database: Database, name: str) -> DeviceCalibration:
    """Gets the current calibration of the given device

    Raises:
        NotFoundError: no matches for {'name': name}
    """
    calibration = await database.get(DeviceCalibration, name)
    if calibration is None:
        raise NotFoundError(f"no matches for '{ {'name': name} }'")
    return calibration
