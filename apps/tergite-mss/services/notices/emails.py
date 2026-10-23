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

from loguru import logger

from libs.storage import And, Database, Eq, In, Inc, Ne, Or, Page, Range, Set, Sort
from services.external.email import BatchEmailGenerator, EmailDetails, EmailResult
from utils.date_time import get_current_timestamp, get_utc_now

from .dtos import EmailStatus, Notice, NoticePreferences, NoticeTypeId


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
        NoticePreferences, where=In("user_id", list(user_ids))
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
            notices = await _find_notices_pending_email(database, batch_size)
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


async def process_email_batch_results(
    database: Database, results: Sequence[EmailResult]
) -> None:
    """Processes the results of an email batch dispatch

    Args:
        results: the results of an email batch dispatch
    """
    successful_ids: List[str] = []
    failed_ids: List[str] = []
    retry_ids: List[str] = []

    for result in results:
        if result.is_success:
            successful_ids.append(result.ref_id)
        elif result.can_retry:
            retry_ids.append(result.ref_id)
        else:
            failed_ids.append(result.ref_id)

    now = get_current_timestamp()
    attempted = [Inc("email_attempts", 1), Set("updated_at", now)]
    success_task = database.update_many(
        Notice,
        where=In("id", successful_ids),
        changes=[*attempted, Set("email_status", EmailStatus.SENT)],
    )
    failure_task = database.update_many(
        Notice,
        where=In("id", failed_ids),
        changes=[*attempted, Set("email_status", EmailStatus.FAILED)],
    )
    retry_task = database.update_many(
        Notice, where=In("id", retry_ids), changes=attempted
    )
    if failed_ids:
        logger.error(f"failed to email notice ids: {failed_ids}")

    resp = await asyncio.gather(
        success_task, failure_task, retry_task, return_exceptions=True
    )
    errs = [v for v in resp if isinstance(v, Exception)]
    if errs:
        logger.exception(f"errors updating notices: {errs}")


async def _find_notices_pending_email(database: Database, limit: int) -> List[Notice]:
    """Gets the notices that are yet to be sent as emails

    Args:
        limit: the maximum number of notices to return

    Returns:
        the list of notices that are yet to be sent as emails
    """
    now = get_utc_now()
    return await database.find(
        Notice,
        where=And(
            Eq("email_status", EmailStatus.PENDING),
            Ne("user_id", None),
            Or(Eq("expires_at", None), Range("expires_at", gt=now)),
        ),
        sort=[Sort("updated_at")],
        page=Page(limit=limit),
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
    from beanie import PydanticObjectId

    from services.auth.users.dtos import User

    user_ids = {PydanticObjectId(notice.user_id) for notice in notices}
    users = await User.find({"_id": {"$in": list(user_ids)}}).to_list()
    user_emails_map = {str(v.id): v.email for v in users}

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
            # this attempt counts towards the maximum
            can_retry=v.email_attempts + 1 < max_attempts,
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
