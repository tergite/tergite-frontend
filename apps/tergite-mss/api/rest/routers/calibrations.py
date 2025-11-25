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

from api.rest.dependencies import CurrentSystemUserProjectDep, MongoDbDep
from services import calibration as calibration_service
from services.calibration.dtos import (
    DeviceCalibrationCreate,
    DeviceCalibrationQuery,
)
from utils.api import PaginatedListResponse

router = APIRouter(prefix="/calibrations", tags=["calibrations"])


@router.get("/")
async def get_many(
    db: MongoDbDep,
    query: DeviceCalibrationQuery = Depends(),
    skip: int = 0,
    limit: Optional[int] = None,
    sort: List[str] = Query(("-last_calibrated",)),
):
    """Gets a paginated list of calibration result sets that fulfill a given set of filters

    Args:
        db: the mongo db database from which to get the calibration results
        query: the query params for getting the calibration result sets
        skip: the number of records to skip
        limit: the maximum number of records to return
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ("-last_calibrated",)
            To add multiple fields to sort by, repeat the same query parameter in the url e.g. "query=tom&q=dick&q=harry"

    Returns:
        the paginated result of the matched device calibration results
    """
    filters = query.model_dump()

    data = await calibration_service.get_latest_many(
        db, filters=filters, limit=limit, skip=skip, sort=sort
    )
    return PaginatedListResponse(skip=skip, limit=limit, data=data).model_dump(
        mode="json", exclude_data_none_fields=False
    )


@router.get("/{name}")
async def read_one(db: MongoDbDep, name: str):
    record = await calibration_service.get_one(db, name)
    return record.model_dump(mode="json")
