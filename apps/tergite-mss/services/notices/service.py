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
#
from copy import deepcopy
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

import pymongo
from beanie import PydanticObjectId, init_beanie
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.auth.users.dtos import USER_DB_COLLECTION
from services.notices.dtos import Notice, NoticeCreate, NOTICE_DB_COLLECTION
from utils.date_time import get_current_timestamp
from utils import mongodb as mongodb_utils
from utils.exc import NotFoundError


async def dismiss_notice(
    db: AsyncIOMotorDatabase, pk: PydanticObjectId, user_id: PydanticObjectId
) -> Notice:
    """Dismisses the notice for the given user

    Args:
        db: the mongo database where the notices are stored
        pk: the id of the notice
        user_id: the ID of the user to dismiss the notice for

    Returns:
        the updated notice

    Raises:
        NotFoundError: if the notice does not exist
    """
    notice = await db[NOTICE_DB_COLLECTION].find_one_and_update(
        {"_id": pk},
        {
            "$addToSet": {"dismissed_by": user_id},
            "$set": {"updated_at": get_current_timestamp()},
        },
        return_document=pymongo.ReturnDocument.AFTER,
    )

    if notice is None:
        raise NotFoundError(f"notice of ID '{pk}' not found")

    return Notice.model_validate(notice)


async def delete_notice(db: AsyncIOMotorDatabase, pk: PydanticObjectId) -> Notice:
    """Deletes the notice

    Args:
        db: the mongo database where the notices are stored
        pk: the id of the notice

    Returns:
        the deleted notice

    Raises:
        NotFoundError: if the notice does not exist
    """
    notice = await db[NOTICE_DB_COLLECTION].find_one_and_delete({"_id": pk})
    if notice is None:
        raise NotFoundError(f"notice of ID '{pk}' not found")

    return Notice.model_validate(notice)


async def publish_notice(
    db: AsyncIOMotorDatabase, current_user_id: PydanticObjectId, payload: NoticeCreate
) -> Notice:
    """Creates a new notice in the database

    Args:
        db: the mongo database where the notices are stored
        current_user_id: the ID of the current user
        payload: the notice payload

    Returns:
        the created notice
    """
    target_user_emails = payload.target_user_emails
    data = payload.model_dump(exclude={"target_user_emails"})
    target_user_ids: Optional[List[PydanticObjectId]] = None

    if target_user_emails:
        cursor = db[USER_DB_COLLECTION].find(
            {"email": {"$in": target_user_emails}}, {"_id": 1}
        )
        target_user_ids = [v["_id"] for v in await cursor.to_list()]

    notice = Notice(**data, created_by=current_user_id, target_user_ids=target_user_ids)
    await notice.create()
    return notice


async def find_many_notices(
    db: AsyncIOMotorDatabase,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    skip: int = 0,
    sort: List[str] = (),
    user_id: Optional[PydanticObjectId] = None,
    min_start_utc: Optional[datetime] = None,
    max_start_utc: Optional[datetime] = None,
    min_expires_utc: Optional[datetime] = None,
    max_expires_utc: Optional[datetime] = None,
    include_dismissed: bool = False,
) -> List[Notice]:
    """Gets many notices from the db

    Args:
        db: the mongo database from which to get the records
        filters: the mongodb-like filters to use to extract the notices
        limit: the number of results to return: default = None meaning all of them
        skip: the number of records to skip; default = 0
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ()
        user_id: the ID of the user whose notices we might be interested in
        min_start_utc: the minimum UTC timestamp that the notice should start
        max_start_utc: the maximum UTC timestamp that the notice should start
        min_expires_utc: the minimum UTC timestamp that the notice should expire
        max_expires_utc: the maximum UTC timestamp that the notice should expire
        include_dismissed: whether to include dismissed notices; defaults to False

    Returns:
        a list of the notices got

    Raises:
        ValidationError: final results are not valid Notice objects
    """
    filters = _merge_filters(
        filters,
        user_id=user_id,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        min_expires_utc=min_expires_utc,
        max_expires_utc=max_expires_utc,
        include_dismissed=include_dismissed,
    )

    return await mongodb_utils.find(
        db[NOTICE_DB_COLLECTION],
        filters=filters,
        limit=limit,
        skip=skip,
        sort=sort,
        schema=Notice,
    )


async def count_many_notices(
    db: AsyncIOMotorDatabase,
    filters: Optional[Dict[str, Any]] = None,
    user_id: Optional[PydanticObjectId] = None,
    min_start_utc: Optional[datetime] = None,
    max_start_utc: Optional[datetime] = None,
    min_expires_utc: Optional[datetime] = None,
    max_expires_utc: Optional[datetime] = None,
    include_dismissed: bool = False,
) -> int:
    """Gets the number of notices that match the given query

    Args:
        db: the mongo database from which to get the records
        filters: the mongodb-like filters to use to extract the notices
        user_id: the ID of the user whose notices we might be interested in
        min_start_utc: the minimum UTC timestamp that the notice should start
        max_start_utc: the maximum UTC timestamp that the notice should start
        min_expires_utc: the minimum UTC timestamp that the notice should expire
        max_expires_utc: the maximum UTC timestamp that the notice should expire
        include_dismissed: whether to include dismissed notices; defaults to False

    Returns:
        a number of matched records
    """
    filters = _merge_filters(
        filters,
        user_id=user_id,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        min_expires_utc=min_expires_utc,
        max_expires_utc=max_expires_utc,
        include_dismissed=include_dismissed,
    )
    return await db[NOTICE_DB_COLLECTION].count_documents(filters)


async def get_one_notice(db: AsyncIOMotorDatabase, pk: PydanticObjectId) -> Notice:
    """Gets the notice of the given pk

    Args:
        db: the mongo database where the notice information is stored
        pk: the ID of the notice to return

    Returns:
        the notice

    Raises:
        ValidationError: if the final result could not be validated as a Notice
        NotFoundError: no matches for {_id: '<pk>'}
    """
    return await mongodb_utils.find_one(
        db[NOTICE_DB_COLLECTION], {"_id": pk}, schema=Notice
    )


async def on_startup(db: AsyncIOMotorDatabase):
    """Runs init operations when the application is starting up"""
    await init_beanie(
        database=db,
        document_models=[
            Notice,
        ],
    )


def _merge_filters(
    filters: Optional[Dict[str, Any]] = None,
    user_id: Optional[PydanticObjectId] = None,
    min_start_utc: Optional[datetime] = None,
    max_start_utc: Optional[datetime] = None,
    min_expires_utc: Optional[datetime] = None,
    max_expires_utc: Optional[datetime] = None,
    include_dismissed: bool = False,
) -> Dict[str, Any]:
    """Combines the filters with the key-word arguments passed"""
    result = deepcopy(filters)
    if result is None:
        result = {}

    if user_id:
        if not include_dismissed:
            _nested_append(result, path=("dismissed_by", "$nin"), value=user_id)

        _nested_append(result, path=("target_user_ids", "$in"), value=user_id)

    if min_start_utc:
        _nested_insert(result, path=("starts_at", "$gte"), value=min_start_utc)

    if max_start_utc:
        _nested_insert(result, path=("starts_at", "$lte"), value=max_start_utc)

    if min_expires_utc:
        _nested_insert(result, path=("expires_at", "$gte"), value=min_expires_utc)

    if max_expires_utc:
        _nested_insert(result, path=("expires_at", "$lte"), value=max_expires_utc)

    return result


def _nested_append(dst: Dict[str, Any], path: Tuple[str, ...], value: Any):
    """Appends a value to a list at a given path in a nested dict

    Args:
        dst: the nested dict in which to insert the value
        path: the path of the value to append
        value: the value to append
    """
    collection = dst
    for segment in path[:-1]:
        collection = collection.setdefault(segment, {})

    inner_list = collection.setdefault(path[-1], [])
    inner_list.append(value)


def _nested_insert(dst: Dict[str, Any], path: Tuple[str, ...], value: Any):
    """Inserts a value at a given path in a nested dict

    Args:
        dst: the nested dict in which to insert the value
        path: the path of the value to insert
        value: the value to insert
    """
    collection = dst
    for segment in path[:-1]:
        collection = collection.setdefault(segment, {})

    collection[path[-1]] = value
