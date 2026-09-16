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
from typing import Dict, List, Sequence

from beanie import PydanticObjectId
from beanie.odm.operators.find.comparison import In
from loguru import logger

from services.external.email import BatchEmailGenerator, EmailDetails, EmailResult
from services.notices import EmailStatus, Notice, NoticePreferences
from services.notices.dtos import NoticeTypeId
from utils.date_time import get_current_timestamp, get_utc_now


async def get_email_preferences_map(
    notice_type: NoticeTypeId,
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


async def get_pending_email_batches(
    batch_size: int, dashboard_url: str, app_name: str, max_attempts: int
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
        notices = await _find_notices_pending_email(batch_size)
        batch = await _to_email_details(
            notices,
            dashboard_url=dashboard_url,
            app_name=app_name,
            max_attempts=max_attempts,
        )
        yield batch
        await asyncio.sleep(1)


async def process_email_batch_results(results: Sequence[EmailResult]) -> None:
    """Processes the results of an email batch dispatch

    Args:
        results: the results of an email batch dispatch
    """
    successful_ids: List[PydanticObjectId] = []
    failed_ids: List[PydanticObjectId] = []
    retry_ids: List[PydanticObjectId] = []

    for result in results:
        if result.is_success:
            successful_ids.append(result.id)
        elif result.can_retry:
            retry_ids.append(result.id)
        else:
            failed_ids.append(result.id)

    # update successful
    now = get_utc_now()
    success_task = (
        Notice.find(In(Notice.id, successful_ids))
        .inc({Notice.email_attempts: 1})
        .set(
            {
                Notice.email_status: EmailStatus.SENT,
                Notice.updated_at: now,
            }
        )
    )
    failure_task = (
        Notice.find(In(Notice.id, failed_ids))
        .inc({Notice.email_attempts: 1})
        .set(
            {
                Notice.email_status: EmailStatus.FAILED,
                Notice.updated_at: now,
            }
        )
    )
    retry_task = (
        Notice.find(In(Notice.id, retry_ids))
        .inc({Notice.email_attempts: 1})
        .set({Notice.updated_at: now})
    )
    if failed_ids:
        logger.exception(f"failed to email notice ids: {failed_ids}")

    resp = await asyncio.gather(
        success_task, failure_task, retry_task, return_exceptions=True
    )
    errs = [v for v in resp if isinstance(v, Exception)]
    if errs:
        logger.exception(f"errors updating notices: {errs}")


async def _find_notices_pending_email(limit: int) -> List[Notice]:
    """Gets the notices that are yet to be sent as emails

    Args:
        limit: the maximum number of notices to return

    Returns:
        the list of notices that are yet to be sent as emails
    """
    now = get_current_timestamp()

    return (
        await Notice.find(
            {
                "email_status": EmailStatus.PENDING,
                "user_id": {"$ne": None},
                "expires_at": {"$or": [{"$ne": None}, {"$gt": now}]},
            },
            limit=limit,
        )
        .sort("updated_at")
        .to_list()
    )


async def _to_email_details(
    notices: Sequence[Notice], dashboard_url: str, app_name: str, max_attempts: int
) -> List[EmailDetails]:
    """Converts a given list of notice objects to a list of EmailDetails

    Each EmailDetails instance is associated with a given notice instance

    Args:
        notices: the list of notice objects
        dashboard_url: the URL of the dashboard
        app_name: the name of the application
        max_attempts: the maximum number of attempts of sending each email notice

    Returns:
        the list of EmailDetails
    """
    from services.auth.users.dtos import User

    user_ids = [notice.user_id for notice in notices]
    users = await User.find({"_id": {"$in": list(set(user_ids))}}).to_list()
    user_emails_map = {v.id: v.email for v in users}

    return [
        EmailDetails(
            to=user_emails_map[v.user_id],
            subject=v.title,
            body=_to_email_body(v, dashboard_url, app_name),
            ref_id=v.id,
            can_retry=v.email_attempts < max_attempts,
        )
        for v in notices
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
    return f""""
{notice.title}

{notice.body}

See it in the dashboard: {dashboard_url}

--
You are receiving this because of activity on your {app_name} account.
"""
