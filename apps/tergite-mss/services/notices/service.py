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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pymongo
from beanie import PydanticObjectId, init_beanie
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

import settings
from services.external import email as email_service
from services.notices.dtos import (
    NOTICE_DB_COLLECTION,
    CustomNoticeCreate,
    EmailStatus,
    Notice,
    NoticePreferences,
    NoticeTemplate,
    NoticeType,
    RefType,
)
from services.notices.utils.templates import get_template
from utils import mongodb as mongodb_utils
from utils.date_time import get_current_timestamp, get_utc_now
from utils.exc import NotFoundError


async def mark_read_one(
    db: AsyncIOMotorDatabase,
    pk: PydanticObjectId,
    user_id: PydanticObjectId,
    is_read: bool,
) -> Notice:
    """Updates the read status of the notice for the given user

    Args:
        db: the mongo database where the notices are stored
        pk: the id of the notice
        user_id: the ID of the user to dismiss the notice for
        is_read: whether the notice was read or not

    Returns:
        the updated notice

    Raises:
        NotFoundError: if the notice does not exist
    """
    now = get_current_timestamp()
    read_at = now if is_read else None

    notice = await db[NOTICE_DB_COLLECTION].find_one_and_update(
        {"_id": pk},
        {
            "$set": {
                "read_at": {
                    "$cond": {
                        "if": {"$eq": ["$type", NoticeType.CUSTOM_BROADCAST]},
                        "then": None,
                        "else": read_at,
                    }
                },
                "updated_at": now,
            },
            "$addToSet": {"dismissed_by": user_id},
        },
        return_document=pymongo.ReturnDocument.AFTER,
    )

    if notice is None:
        raise NotFoundError(f"notice of ID '{pk}' not found")

    return Notice.model_validate(notice)


async def mark_read_many(
    db: AsyncIOMotorDatabase,
    user_id: PydanticObjectId,
    is_read: bool,
    filters: Optional[Dict[str, Any]] = None,
    min_start_utc: Optional[datetime] = None,
    max_start_utc: Optional[datetime] = None,
    min_expires_utc: Optional[datetime] = None,
    max_expires_utc: Optional[datetime] = None,
    types: Optional[Sequence[NoticeType]] = None,
) -> int:
    """Marks every one of the user's notifications read or unread

    Args:
        db: the mongo database from which to get the records
        user_id: the recipient whose notices are to be updated
        is_read: True to mark read, False to mark unread
        filters: the mongodb-like filters to use to extract the notices
        min_start_utc: the minimum UTC timestamp that the notice should start
        max_start_utc: the maximum UTC timestamp that the notice should start
        min_expires_utc: the minimum UTC timestamp that the notice should expire
        max_expires_utc: the maximum UTC timestamp that the notice should expire
        types: the notice types to filter by; default = None i.e. any

    Returns:
        the number of notifications updated
    """
    if is_read:
        # filter for the unread
        _nested_append(filters, path=("dismissed_by", "$nin"), value=user_id)
    else:
        # filter for the read
        _nested_append(filters, path=("dismissed_by", "$in"), value=user_id)

    filters = _merge_filters(
        filters,
        user_id=user_id,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        min_expires_utc=min_expires_utc,
        max_expires_utc=max_expires_utc,
        include_dismissed=True,
        types=types,
    )

    now = get_current_timestamp()
    read_at = now if is_read else None

    result = await db[NOTICE_DB_COLLECTION].update_many(
        filters,
        {
            "$set": {
                "read_at": {
                    "$cond": {
                        "if": {"$eq": ["$type", NoticeType.CUSTOM_BROADCAST]},
                        "then": None,
                        "else": read_at,
                    }
                },
                "updated_at": now,
            },
            "$addToSet": {"dismissed_by": user_id},
        },
    )
    return result.modified_count


async def mark_ref_handled(
    db: AsyncIOMotorDatabase, ref_type: RefType, ref_id: PydanticObjectId
) -> int:
    """Marks read every unread notice associated with a given reference of a certain id and type

    This is useful in bulk clearing notifications that no longer have any consequence,
    without having users dismiss them manually. An example is a user request to create
    a project. If the system admin created that project then there would be no need
    for that admin to go clear all the notices manually.

    Args:
        db: the mongo database from which to get the records
        ref_type: the type of the reference
        ref_id: the ID of the associated reference object that has been decided

    Returns:
        the number of notices updated
    """
    now = get_current_timestamp()
    filters = {
        "ref_id": ref_id,
        "ref_type": ref_type,
        "read_at": None,
        "expires_at": {"$or": [{"$eq": None}, {"$gte": now}]},
    }

    result = await db[NOTICE_DB_COLLECTION].update_many(
        filters,
        {
            "$set": {
                "read_at": {
                    "$cond": {
                        "if": {"$eq": ["$type", NoticeType.CUSTOM_BROADCAST]},
                        "then": None,
                        "else": now,
                    }
                },
                "updated_at": now,
                "expires_at": now,
            },
        },
    )

    return result.modified_count


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


async def publish_custom_notice(
    db: AsyncIOMotorDatabase,
    current_user_id: PydanticObjectId,
    payload: CustomNoticeCreate,
) -> List[Notice]:
    """Creates a new notice in the database

    Args:
        db: the mongo database where the notices are stored
        current_user_id: the ID of the current user
        payload: the notice payload

    Returns:
        the created notice
    """
    notices = await payload.to_documents(db, user_id=current_user_id)
    resp = await Notice.insert_many(notices)
    # FIXME: I am not sure if I need to update the ids, but I do so anyway
    for i, pk in enumerate(resp.inserted_ids):
        notices[i].id = pk

    return notices


async def create_system_notice(
    user_ids: Sequence[PydanticObjectId],
    notice_type: NoticeType,
    context: Optional[Dict[str, Any]] = None,
    ref_type: Optional[RefType] = None,
    ref_id: Optional[PydanticObjectId] = None,
    retention_days: int = settings.CONFIG.notifications.retention_days,
    **kwargs,
) -> List[Notice]:
    """Creates a system notice for the given users.

    Never raises: a notification is a side effect of some other operation, and failing to
    deliver one must not fail the operation that triggered it.

    Args:
        user_ids: the recipients; one document is written per user
        notice_type: the notice type, which selects the copy and the channel policy
        context: values interpolated into the copy, also stored for deep links
        ref_type: the reference type that is associated with this notice, e.g. a user_request
        ref_id: the unique identifier of the reference in the collection of the given ref_type
        retention_days: the number of days this notice should be retained

    Returns:
        the created notices, or an empty list if none were created
    """
    if len(user_ids) == 0:
        return []

    context = context or {}
    try:
        template = await get_template(notice_type, context)
        email_prefs_map = await _get_email_preferences_map(
            notice_type, user_ids=user_ids
        )

        if not email_service.is_configured():
            email_status_map = {k: EmailStatus.NOT_APPLICABLE for k in user_ids}
        else:
            email_status_map = {
                k: EmailStatus.PENDING if v else EmailStatus.NOT_APPLICABLE
                for k, v in email_prefs_map.items()
            }

        records = [
            Notice(
                user_id=user_id,
                type=notice_type,
                title=template.title,
                body=template.body,
                severity=template.severity,
                ref_type=ref_type,
                ref_id=ref_id,
                context=context,
                email_status=email_status_map[user_id],
                expires_at=get_utc_now() + timedelta(retention_days),
            )
            for user_id in user_ids
        ]
        await Notice.insert_many(records)
        return records
    except Exception:
        logger.exception(f"failed to emit {notice_type} notification")
        return []


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
    types: Optional[Sequence[NoticeType]] = None,
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
        types: the notice types to filter by; default = None i.e. any

    Returns:
        a list of the notices got

    Raises:
        ValidationError: final results are not valid Notice objects
    """
    # FIXME: the system notices default sort was ("-created_at")
    filters = _merge_filters(
        filters,
        user_id=user_id,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        min_expires_utc=min_expires_utc,
        max_expires_utc=max_expires_utc,
        include_dismissed=include_dismissed,
        types=types,
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
    types: Optional[Sequence[NoticeType]] = None,
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
        types: the notice types to filter by; default = None i.e. any

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
        types=types,
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


async def get_email_preferences(
    user_id: PydanticObjectId,
) -> Dict[NoticeType, bool]:
    """The user's effective preferences, with defaults filled in for every type

    Args:
        user_id: the user whose preferences are wanted

    Returns:
        a full map of type to preferences
    """
    record = await NoticePreferences.find_one({"user_id": user_id})
    prefs_in_db = record.email_prefs if record is not None else {}

    return {k: prefs_in_db.get(k, True) for k in NoticeType}


async def set_email_preferences(
    user_id: PydanticObjectId, prefs: Dict[NoticeType, bool]
) -> Dict[NoticeType, bool]:
    """Applies a partial preference update

    Args:
        user_id: the user whose preferences are updated
        prefs: the types to change; types not named keep their current value

    Returns:
        the user's full effective preferences after the update
    """
    record = await NoticePreferences.find_one({"user_id": user_id})
    current = record.email_prefs if record is not None else {}
    current.update(prefs)
    await NoticePreferences.find_one({"user_id": user_id}).upsert(
        {
            "$set": {
                "email_prefs": current,
                "updated_at": get_current_timestamp(),
            }
        },
        on_insert=NoticePreferences(user_id=user_id, email_prefs=current),
    )
    return current


async def on_startup(db: AsyncIOMotorDatabase):
    """Runs init operations when the application is starting up"""
    await init_beanie(
        database=db,
        document_models=[
            Notice,
            NoticePreferences,
            NoticeTemplate,
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
    types: Optional[Sequence[NoticeType]] = None,
) -> Dict[str, Any]:
    """Combines the filters with the key-word arguments passed"""
    result = deepcopy(filters)
    if result is None:
        result = {}

    if user_id:
        if not include_dismissed:
            _nested_append(result, path=("dismissed_by", "$nin"), value=user_id)

        # either broadcast notices or those sent directly to user
        _nested_append(result, path=("user_id", "$in"), value=user_id)
        _nested_append(result, path=("user_id", "$in"), value=None)

    if min_start_utc:
        _nested_insert(result, path=("starts_at", "$gte"), value=min_start_utc)

    if max_start_utc:
        _nested_insert(result, path=("starts_at", "$lte"), value=max_start_utc)

    if min_expires_utc:
        _nested_insert(result, path=("expires_at", "$gte"), value=min_expires_utc)

    if max_expires_utc:
        _nested_insert(result, path=("expires_at", "$lte"), value=max_expires_utc)

    if types:
        _nested_insert(result, path=("type", "$in"), value=types)

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


async def _get_email_preferences_map(
    notice_type: NoticeType,
    user_ids: Sequence[PydanticObjectId],
) -> Dict[PydanticObjectId, bool]:
    """Retrieves a map of email preferences for the given notice type keyed by user_id

    Args:
        notice_type: the notice type
        user_ids: the IDs of the users

    Returns:
        a map of channel preferences for the given notice type keyed by user_id
    """
    result = NoticePreferences.find({"user_id": {"$in": list(user_ids)}})
    return {
        record.user_id: record.email_prefs.get(notice_type, True)
        async for record in result
    }
