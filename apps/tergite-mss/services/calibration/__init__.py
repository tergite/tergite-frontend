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
from typing import Any, Dict, List, Optional, Tuple

import pymongo
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ReturnDocument

from utils import mongodb as mongodb_utils

from .dtos import DeviceCalibration, DeviceCalibrationCreate

_LOGS_COLLECTION = "calibrations_logs"
_MAIN_COLLECTION = "calibrations"


async def on_startup(db: AsyncIOMotorDatabase):
    """Initializes the collections for the calibrations service

    Args:
        db: the mongodb database instance
    """
    calibrations: AsyncIOMotorCollection = db[_MAIN_COLLECTION]
    calibrations_log: AsyncIOMotorCollection = db[_LOGS_COLLECTION]

    await calibrations.create_index([("name", pymongo.ASCENDING)])
    await calibrations_log.create_index(
        [("name", pymongo.ASCENDING), ("last_calibrated", pymongo.DESCENDING)]
    )


async def insert_one(
    db: AsyncIOMotorDatabase, record: DeviceCalibrationCreate
) -> DeviceCalibration:
    """Inserts into the database a new calibration result set

    Args:
        db: the mongo database
        record: the data to be inserted

    Returns:
        the inserted document
    """
    document = record.model_dump()
    # Save historical calibrations
    # We use insert_one_if_not_exists to ensure idempotency
    await mongodb_utils.insert_one_if_not_exists(
        collection=db[_LOGS_COLLECTION],
        document={**document},
        unique_fields=("name", "last_calibrated"),
    )

    # Save current calibration
    record = await mongodb_utils.update_one(
        collection=db[_MAIN_COLLECTION],
        _filter={"name": document["name"]},
        payload=document,
        return_document=ReturnDocument.AFTER,
        upsert=True,
    )

    return DeviceCalibration.model_validate(record)


async def get_latest_many(
    db: AsyncIOMotorDatabase,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    skip: int = 0,
    sort: List[str] = (),
) -> List[DeviceCalibration]:
    """Gets the current calibration results for all available devices

    Args:
        db: the mongo database
        filters: the mongodb-like filters to use to extract the calibrations
        limit: the number of results to return: default = None meaning all of them
        skip: the number of records to skip; default = 0
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ()

    Returns:
        the list of calibration results
    """
    return await mongodb_utils.find(
        db[_MAIN_COLLECTION],
        filters=filters,
        limit=limit,
        skip=skip,
        sort=sort,
        schema=DeviceCalibration,
    )


async def get_historical_many(
    db: AsyncIOMotorDatabase,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    skip: int = 0,
    sort: List[str] = (),
) -> List[DeviceCalibration]:
    """Gets the current calibration results for all available devices

    Args:
        db: the mongo database
        filters: the mongodb-like filters to use to extract the calibrations
        limit: the number of results to return: default = None meaning all of them
        skip: the number of records to skip; default = 0
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ()

    Returns:
        the list of calibration results
    """
    return await mongodb_utils.find(
        db[_LOGS_COLLECTION],
        filters=filters,
        limit=limit,
        skip=skip,
        sort=sort,
        schema=DeviceCalibration,
    )


async def get_one(db: AsyncIOMotorDatabase, name: str) -> DeviceCalibration:
    """Gets the current calibration results of the given device

    Args:
        db: the mongo database
        name: the name of the device

    Returns:
        the dict of the calibration results
    """
    return await mongodb_utils.find_one(
        db[_MAIN_COLLECTION],
        {"name": name},
        schema=DeviceCalibration,
    )
