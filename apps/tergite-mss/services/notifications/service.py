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
"""Service for per-recipient, event-driven notifications"""
from datetime import timedelta
from typing import Any, Dict, List, Optional, Sequence

from beanie import PydanticObjectId, UpdateResponse, init_beanie
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

import settings
from services.external import email
from utils.date_time import get_current_timestamp, get_utc_now
from utils.exc import NotFoundError

from .dtos import (
    ChannelPrefs,
    EmailStatus,
    Notification,
    NotificationAction,
    NotificationPreferences,
    NotificationType,
)
from .templates import CHANNEL_POLICY, render


async def notify(
    user_ids: Sequence[PydanticObjectId],
    type_: NotificationType,
    context: Optional[Dict[str, Any]] = None,
    action: Optional[NotificationAction] = None,
) -> List[Notification]:
    """Creates one notification per recipient.

    Never raises: a notification is a side effect of some other operation, and failing to
    deliver one must not fail the operation that triggered it.

    Args:
        user_ids: the recipients; one document is written per user
        type_: the notification type, which selects the copy and the channel policy
        context: values interpolated into the copy, also stored for deep links
        action: what the recipient can do about it, if anything

    Returns:
        the created notifications, or an empty list if none were created
    """
    if len(user_ids) == 0:
        return []

    context = context or {}
    try:
        template = render(type_, context)
        wanted = await _recipients_wanting(user_ids, type_)
        if len(wanted) == 0:
            return []

        email_status = await _initial_email_status(wanted, type_)
        records = [
            Notification(
                user_id=user_id,
                type=type_,
                title=template.title,
                body=template.body,
                severity=template.severity,
                action=action,
                context=context,
                email_status=email_status[user_id],
                expires_at=get_utc_now()
                + timedelta(days=settings.CONFIG.notifications.retention_days),
            )
            for user_id in wanted
        ]
        await Notification.insert_many(records)
        return records
    except Exception:
        logger.exception(f"failed to emit {type_} notification")
        return []


async def find_many(
    user_id: PydanticObjectId,
    types: Sequence[NotificationType] = (),
    is_read: Optional[bool] = None,
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Notification]:
    """Gets the given user's notifications, newest first

    Args:
        user_id: the recipient whose notifications are wanted
        types: the types to filter by; default = () i.e. any
        is_read: filter on read state; default = None i.e. either
        skip: the number of records to skip
        limit: the maximum number of records to return

    Returns:
        the matched notifications
    """
    return (
        await Notification.find(
            _filters(user_id, types, is_read), skip=skip, limit=limit
        )
        .sort("-created_at")
        .to_list()
    )


async def count_many(
    user_id: PydanticObjectId,
    types: Sequence[NotificationType] = (),
    is_read: Optional[bool] = None,
) -> int:
    """Counts the given user's notifications matching the filter

    Args:
        user_id: the recipient whose notifications are counted
        types: the types to filter by; default = () i.e. any
        is_read: filter on read state; default = None i.e. either

    Returns:
        the number of matched notifications
    """
    return await Notification.find(_filters(user_id, types, is_read)).count()


async def set_read(
    pk: PydanticObjectId, user_id: PydanticObjectId, is_read: bool
) -> Notification:
    """Marks one of the user's own notifications read or unread

    Args:
        pk: the ID of the notification
        user_id: the recipient, so one user cannot touch another's notifications
        is_read: True to mark read, False to mark unread

    Returns:
        the updated notification

    Raises:
        NotFoundError: notification of ID '{pk}' not found
    """
    read_at = get_current_timestamp() if is_read else None
    result = await Notification.find_one({"_id": pk, "user_id": user_id}).update(
        {"$set": {"read_at": read_at, "updated_at": get_current_timestamp()}},
        response_type=UpdateResponse.NEW_DOCUMENT,
    )
    if result is None:
        raise NotFoundError(f"notification of ID '{pk}' not found")

    return result


async def set_all_read(user_id: PydanticObjectId, is_read: bool) -> int:
    """Marks every one of the user's notifications read or unread

    Args:
        user_id: the recipient whose notifications are updated
        is_read: True to mark read, False to mark unread

    Returns:
        the number of notifications updated
    """
    read_at = get_current_timestamp() if is_read else None
    result = await Notification.find(
        {"user_id": user_id, "read_at": {"$ne": read_at}}
    ).update({"$set": {"read_at": read_at, "updated_at": get_current_timestamp()}})
    return result.modified_count


async def get_preferences(
    user_id: PydanticObjectId,
) -> Dict[NotificationType, ChannelPrefs]:
    """The user's effective preferences, with defaults filled in for every type

    Args:
        user_id: the user whose preferences are wanted

    Returns:
        a full map of type to preferences
    """
    record = await NotificationPreferences.find_one({"user_id": user_id})
    stored = record.prefs if record is not None else {}
    return {
        type_: stored.get(type_, ChannelPrefs(in_app=True, email=policy.email_default))
        for type_, policy in CHANNEL_POLICY.items()
    }


async def set_preferences(
    user_id: PydanticObjectId, prefs: Dict[NotificationType, ChannelPrefs]
) -> Dict[NotificationType, ChannelPrefs]:
    """Applies a partial preference update, ignoring silencing of mandatory types

    Args:
        user_id: the user whose preferences are updated
        prefs: the types to change; types not named keep their current value

    Returns:
        the user's full effective preferences after the update
    """
    current = await get_preferences(user_id)
    for type_, wanted in prefs.items():
        # in-app cannot be silenced where the policy says it is mandatory
        in_app = True if CHANNEL_POLICY[type_].in_app_mandatory else wanted.in_app
        current[type_] = ChannelPrefs(in_app=in_app, email=wanted.email)

    await NotificationPreferences.find_one({"user_id": user_id}).upsert(
        {
            "$set": {
                "prefs": {k.value: v.model_dump() for k, v in current.items()},
                "updated_at": get_current_timestamp(),
            }
        },
        on_insert=NotificationPreferences(user_id=user_id, prefs=current),
    )
    return current


async def on_startup(db: AsyncIOMotorDatabase):
    """Runs init operations when the application is starting up"""
    await init_beanie(
        database=db, document_models=[Notification, NotificationPreferences]
    )


async def _initial_email_status(
    user_ids: Sequence[PydanticObjectId], type_: NotificationType
) -> Dict[PydanticObjectId, EmailStatus]:
    """The email state each notification starts in.

    PENDING makes the notification row its own outbox entry for the sweeper to pick up;
    NOT_APPLICABLE means nothing will ever try to send it.

    Args:
        user_ids: the recipients
        type_: the notification type, whose policy supplies the default

    Returns:
        the starting email status per recipient
    """
    if not email.is_configured():
        return {user_id: EmailStatus.NOT_APPLICABLE for user_id in user_ids}

    records = await NotificationPreferences.find(
        {"user_id": {"$in": list(user_ids)}}
    ).to_list()
    stored = {record.user_id: record.prefs for record in records}
    default = CHANNEL_POLICY[type_].email_default
    return {
        user_id: (
            EmailStatus.PENDING
            if stored.get(user_id, {}).get(type_, ChannelPrefs(email=default)).email
            else EmailStatus.NOT_APPLICABLE
        )
        for user_id in user_ids
    }


def _filters(
    user_id: PydanticObjectId,
    types: Sequence[NotificationType],
    is_read: Optional[bool],
) -> Dict[str, Any]:
    """Builds the mongodb filter for a recipient's notifications"""
    filter_obj: Dict[str, Any] = {"user_id": user_id}
    if len(types) > 0:
        filter_obj["type"] = {"$in": list(types)}
    if is_read is True:
        filter_obj["read_at"] = {"$ne": None}
    elif is_read is False:
        filter_obj["read_at"] = None
    return filter_obj


async def _recipients_wanting(
    user_ids: Sequence[PydanticObjectId], type_: NotificationType
) -> List[PydanticObjectId]:
    """The subset of recipients whose preferences allow this type in-app"""
    if CHANNEL_POLICY[type_].in_app_mandatory:
        return list(dict.fromkeys(user_ids))

    records = await NotificationPreferences.find(
        {"user_id": {"$in": list(user_ids)}}
    ).to_list()
    silenced = {
        record.user_id
        for record in records
        if type_ in record.prefs and not record.prefs[type_].in_app
    }
    return [user_id for user_id in dict.fromkeys(user_ids) if user_id not in silenced]
