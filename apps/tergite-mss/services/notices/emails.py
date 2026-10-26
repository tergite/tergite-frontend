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
import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Sequence

from loguru import logger

from libs.storage import Database
from services.external.email import BatchEmailGenerator, EmailDetails, EmailResult
from utils.date_time import datetime_to_zulu, get_current_timestamp, get_utc_now

from .dtos import EmailStatus, Notice, NoticePreferences, NoticeTypeId

# how long a claim on an email stands before another process takes it over, as the
# claiming process must have stopped
_CLAIM_LIFESPAN = timedelta(minutes=10)


async def get_email_preferences_map(
    database: Database,
    notice_type: NoticeTypeId,
    user_ids: Sequence[str],
) -> Dict[str, bool]:
    """Retrieves a map of email preferences for the given notice type keyed by user_id

    Args:
        notice_type: the notice type
        user_ids: the IDs of the users

    Returns:
        a map of channel preferences for the given notice type keyed by user_id
    """
    records = await database.find(
        NoticePreferences, filter={"user_id": {"$in": list(user_ids)}}
    )
    return {
        record.user_id: record.email_prefs.get(notice_type, True) for record in records
    }


async def get_pending_email_batches(
    database: Database,
    batch_size: int,
    dashboard_url: str,
    app_name: str,
    max_attempts: int,
) -> BatchEmailGenerator:
    """Generates email details batches that are yet to be sent.

    Args:
        batch_size: the size of each the batch
        dashboard_url: the URL of the dashboard
        app_name: the name of the application
        max_attempts: the maximum number of attempts of sending each email

    Returns:
        the Generator of pending email batches
    """
    while True:
        try:
            notices = await claim_pending_emails(database, limit=batch_size)
            batch = await _to_email_details(
                database,
                notices,
                dashboard_url=dashboard_url,
                app_name=app_name,
                max_attempts=max_attempts,
            )
        except Exception:
            # an async generator that raises is finished, and so would be all emailing
            logger.exception("failed to get the pending notice emails")
            batch = []

        yield batch
        await asyncio.sleep(1)


async def claim_pending_emails(database: Database, limit: int) -> List[Notice]:
    """Claims up to limit pending emails for this process, leaving any another claims first

    Each claim counts an attempt, so a process that stops while sending loses it.
    """
    notices = await _find_notices_pending_email(database, limit)
    now = get_current_timestamp()
    claimed = [
        await database.update_one(
            Notice,
            filter={"id": v.id, "email_attempts": v.email_attempts},
            update={
                "$inc": {"email_attempts": 1},
                "$set": {"email_status": EmailStatus.SENDING, "updated_at": now},
            },
        )
        for v in notices
    ]
    return [v for v in claimed if v is not None]


async def process_email_batch_results(
    database: Database, results: Sequence[EmailResult]
) -> None:
    """Processes the results of an email batch dispatch

    Args:
        results: the results of an email batch dispatch
    """
    ids = _partition_results(results)
    if ids.failed:
        logger.error(f"failed to email notice ids: {ids.failed}")

    outcomes = await asyncio.gather(
        _set_email_status(database, ids.sent, status=EmailStatus.SENT),
        _set_email_status(database, ids.failed, status=EmailStatus.FAILED),
        _set_email_status(database, ids.retried, status=EmailStatus.PENDING),
        return_exceptions=True,
    )
    errors = [v for v in outcomes if isinstance(v, Exception)]
    if errors:
        logger.exception(f"errors updating notices: {errors}")


async def _find_notices_pending_email(database: Database, limit: int) -> List[Notice]:
    """Gets the notices whose emails are pending, or claimed by a process that stopped

    Args:
        limit: the maximum number of notices to return

    Returns:
        the list of notices that are yet to be sent as emails
    """
    now = get_utc_now()
    stale_claim = {
        "email_status": EmailStatus.SENDING,
        "updated_at": {"$lt": datetime_to_zulu(now - _CLAIM_LIFESPAN)},
    }
    return await database.find(
        Notice,
        filter={
            "user_id": {"$ne": None},
            "$and": [
                {"$or": [{"email_status": EmailStatus.PENDING}, stale_claim]},
                {"$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}]},
            ],
        },
        sort=["updated_at"],
        limit=limit,
    )


async def _to_email_details(
    database: Database,
    notices: Sequence[Notice],
    dashboard_url: str,
    app_name: str,
    max_attempts: int,
) -> List[EmailDetails]:
    """Converts a given list of notice objects to a list of EmailDetails

    Each EmailDetails instance is associated with a given notice instance.
    Notices of users without an email address are marked failed, as no retry would help.

    Args:
        notices: the list of notice objects
        dashboard_url: the URL of the dashboard
        app_name: the name of the application
        max_attempts: the maximum number of attempts of sending each email notice

    Returns:
        the list of EmailDetails
    """
    # imported here to avoid a circular import, as the auth service imports this one
    from services.auth.users.dtos import User

    user_ids = list({notice.user_id for notice in notices})
    users = await database.find(User, filter={"id": {"$in": user_ids}})
    user_emails_map = {user.id: user.email for user in users}

    unreachable_ids = [v.id for v in notices if v.user_id not in user_emails_map]
    if unreachable_ids:
        await process_email_batch_results(
            database,
            [
                EmailResult(error=KeyError("no such user"), ref_id=v, can_retry=False)
                for v in unreachable_ids
            ],
        )

    return [
        EmailDetails(
            to=user_emails_map[v.user_id],
            subject=v.title,
            body=_to_email_body(v, dashboard_url, app_name),
            ref_id=v.id,
            # its claim counted this attempt
            can_retry=v.email_attempts < max_attempts,
        )
        for v in notices
        if v.user_id in user_emails_map
    ]


def _to_email_body(notice: Notice, dashboard_url: str, app_name: str) -> str:
    """Converts a given notice object to a body of the email

    Args:
        notice: the notice object
        dashboard_url: the URL of the dashboard
        app_name: the name of the application

    Returns:
        the body of the email for the given notice
    """
    return f"""
{notice.title}

{notice.body}

See it in the dashboard: {dashboard_url}

--
You are receiving this because of activity on your {app_name} account.
"""


@dataclass(frozen=True)
class _ResultIds:
    sent: List[str]
    failed: List[str]
    retried: List[str]


def _partition_results(results: Sequence[EmailResult]) -> _ResultIds:
    """Gets the notice ids of the emails sent, failed for good, and to be retried"""
    return _ResultIds(
        sent=[v.ref_id for v in results if v.is_success],
        failed=[v.ref_id for v in results if not v.is_success and not v.can_retry],
        retried=[v.ref_id for v in results if not v.is_success and v.can_retry],
    )


async def _set_email_status(
    database: Database, ids: List[str], status: EmailStatus
) -> None:
    await database.update_many(
        Notice,
        filter={"id": {"$in": ids}},
        update={
            "$set": {"email_status": status, "updated_at": get_current_timestamp()}
        },
    )
