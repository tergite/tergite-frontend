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
"""Email delivery for notifications, using the notification row as the outbox.

Sending inline would make an approve click as slow as the mail server and fail the click
when the mail server is down. Instead each notification carries its own delivery state and
a single background task drains the pending ones, which also means a restart resumes rather
than loses whatever was queued.

Rows are not claimed before sending, so a second MSS process sweeping the same database would
send some notifications twice. One process per deployment is the assumption.
"""
import asyncio
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from loguru import logger

import settings
from services.external import email
from utils.date_time import get_current_timestamp

from .dtos import EmailStatus, Notification
from .templates import render_email

_task: Optional[asyncio.Task] = None


async def send_pending(limit: int = 50) -> int:
    """Sends one batch of pending emails.

    Never raises: a failure is recorded on the row and retried on a later sweep, up to
    `notifications.email_retry_limit` attempts.

    Args:
        limit: the maximum number of notifications to attempt in this batch

    Returns:
        the number sent successfully
    """
    if not email.is_configured():
        return 0

    pending: List[Notification] = (
        await Notification.find({"email_status": EmailStatus.PENDING}, limit=limit)
        .sort("updated_at")
        .to_list()
    )
    if len(pending) == 0:
        return 0

    addresses = await _addresses_for([notification.user_id for notification in pending])
    dashboard_url = settings.CONFIG.notifications.dashboard_url
    retry_limit = settings.CONFIG.notifications.email_retry_limit
    sent = 0

    for notification in pending:
        address = addresses.get(notification.user_id)
        if address is None:
            # no address to send to, so no amount of retrying will help
            await _record(notification, EmailStatus.FAILED)
            continue

        try:
            await email.send(
                to_address=address,
                subject=notification.title,
                body=render_email(notification.title, notification.body, dashboard_url),
            )
        except Exception:
            attempts = notification.email_attempts + 1
            status = (
                EmailStatus.FAILED if attempts >= retry_limit else EmailStatus.PENDING
            )
            logger.exception(
                f"failed to email notification {notification.id} "
                f"(attempt {attempts}/{retry_limit})"
            )
            await _record(notification, status, attempts=attempts)
            continue

        await _record(
            notification, EmailStatus.SENT, attempts=notification.email_attempts + 1
        )
        sent += 1

    return sent


def start_sweeper() -> None:
    """Starts the background sweep, if the email channel is configured"""
    global _task
    if not email.is_configured() or _task is not None:
        return

    _task = asyncio.create_task(_sweep_forever())
    logger.info("Notification email sweeper started")


async def stop_sweeper() -> None:
    """Stops the background sweep"""
    global _task
    if _task is None:
        return

    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
    logger.info("Notification email sweeper stopped")


async def _sweep_forever() -> None:
    """Drains the outbox on an interval until cancelled"""
    interval = settings.CONFIG.notifications.email_sweep_interval
    while True:
        try:
            await send_pending()
        except asyncio.CancelledError:
            raise
        except Exception:
            # the loop must outlive any single bad sweep
            logger.exception("notification email sweep failed")
        await asyncio.sleep(interval)


async def _addresses_for(
    user_ids: List[PydanticObjectId],
) -> Dict[PydanticObjectId, str]:
    """Maps recipient IDs to email addresses in one query"""
    # imported here because services.auth reaches back into this package at import time
    from services.auth.users.dtos import User

    users = await User.find({"_id": {"$in": list(set(user_ids))}}).to_list()
    return {user.id: user.email for user in users}


async def _record(
    notification: Notification, status: EmailStatus, attempts: Optional[int] = None
) -> None:
    """Writes the delivery outcome back onto the notification"""
    update = {"email_status": status, "updated_at": get_current_timestamp()}
    if attempts is not None:
        update["email_attempts"] = attempts

    await Notification.find_one({"_id": notification.id}).update({"$set": update})
