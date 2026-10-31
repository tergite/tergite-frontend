# This code is part of Tergite
#
# (C) Copyright Miroslav Dobsicek 2020
# (C) Copyright Simon Genne, Arvid Holmqvist, Bashar Oumari, Jakob Ristner,
#               Björn Rosengren, and Jakob Wik 2022 (BSc project)
# (C) Copyright Fabian Forslund, Niklas Botö 2022
# (C) Copyright Abdullah-Al Amin 2022
# (C) Copyright Martin Ahindura 2023
# (C) Chalmers Next Labs AB 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from api.dependencies import DatabaseDep
from services import calibration as calibration_service
from services.calibration import (
    DeviceCalibration,
    DeviceCalibrationQuery,
)
from utils.api import PaginatedListResponse, get_paginated_json

router = APIRouter(prefix="/calibrations", tags=["calibrations"])


@router.get("/", responses={200: {"model": PaginatedListResponse[DeviceCalibration]}})
async def get_many(
    database: DatabaseDep,
    query: DeviceCalibrationQuery = Depends(),
    skip: int = 0,
    limit: Optional[int] = None,
    sort: List[str] = Query(("-last_calibrated",)),
):
    """Gets a paginated list of calibration result sets that fulfill a given set of filters

    Args:
        database: the database where the calibrations are stored
        query: the query params for getting the calibration result sets
        skip: the number of records to skip
        limit: the maximum number of records to return
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ("-last_calibrated",)
            To add multiple fields to sort by, repeat the same query parameter in the url e.g. "query=tom&q=dick&q=harry"

    Returns:
        the paginated result of the matched device calibration results
    """
    data = await calibration_service.find_latest_calibrations(
        database,
        query=query,
        sort=sort,
        skip=skip,
        limit=limit,
    )
    return get_paginated_json(data, skip=skip, limit=limit, should_exclude_none=False)


@router.get("/{name}", responses={200: {"model": DeviceCalibration}})
async def read_one(database: DatabaseDep, name: str):
    """Gets the current calibration of the device of the given name

    Args:
        database: the database where the calibrations are stored
        name: the name of the device

    Returns:
        the device's calibration

    Raises:
        404: the device has no calibration
    """
    record = await calibration_service.get_one(database, name)
    return record.model_dump(mode="json")
