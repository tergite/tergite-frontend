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
"""Integration tests for the email copies of notices"""

import time
from typing import Callable

import aiosmtplib

import settings
from libs.storage import generate_id
from services.notices import EmailStatus, Notice, NoticeSeverity
from tests._utils.auth import (
    TEST_PROJECT_ID,
    TEST_PROJECT_NAME,
    TEST_USER_EMAIL,
    TEST_USER_ID,
)
from tests._utils.env import TEST_APP_CONFIG
from tests._utils.notices import get_user_notices
from utils.date_time import get_current_timestamp

_ACCESS_REQUEST = {
    "type": "project-access",
    "resource_id": TEST_PROJECT_ID,
    "reason": "let me in",
}


def test_email_is_queued_when_configured(
    client, outsider_jwt_cookie, db, paused_email_sweeper
):
    """A configured email channel makes the notice its own outbox entry"""
    with client as client:
        client.post("/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST)

        assert get_user_notices(db, TEST_USER_ID)[0].email_status == (
            EmailStatus.PENDING
        )


def test_email_is_not_queued_when_unconfigured(
    client, outsider_jwt_cookie, db, unconfigured_email, smtp
):
    """Without an email config nothing is queued and nothing is sent"""
    with client as client:
        client.post("/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST)
        time.sleep(0.2)

        assert get_user_notices(db, TEST_USER_ID)[0].email_status == (
            EmailStatus.NOT_APPLICABLE
        )
        smtp.assert_not_awaited()


def test_email_is_not_queued_when_opted_out(
    client, outsider_jwt_cookie, user_jwt_cookie, db, paused_email_sweeper
):
    """An opt-out is honoured when the notice is written, so no email is ever queued"""
    with client as client:
        client.put(
            "/me/notices/preferences/",
            cookies=user_jwt_cookie,
            json={"project-access-requested": False},
        )
        client.post("/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST)

        assert get_user_notices(db, TEST_USER_ID)[0].email_status == (
            EmailStatus.NOT_APPLICABLE
        )


def test_sweeper_sends_a_queued_email(client, outsider_jwt_cookie, db, smtp):
    """A request notifies the project admin, who is then emailed a link to the dashboard"""
    email_conf = TEST_APP_CONFIG["email"]

    with client as client:
        client.post("/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST)
        _wait_for(
            lambda: (
                get_user_notices(db, TEST_USER_ID)[0].email_status == EmailStatus.SENT
            )
        )

    message = smtp.call_args.args[0]
    assert message["To"] == TEST_USER_EMAIL
    assert message["From"] == (
        f"{email_conf['from_name']} <{email_conf['from_address']}>"
    )
    assert message["Subject"] == f"Access request for {TEST_PROJECT_NAME}"
    assert TEST_APP_CONFIG["notices"]["dashboard_url"] in message.get_content()
    assert get_user_notices(db, TEST_USER_ID)[0].email_attempts == 1


def test_refused_email_stays_pending_for_a_retry(client, outsider_jwt_cookie, db, smtp):
    """A mail server refusing an email must not lose it"""
    smtp.side_effect = aiosmtplib.SMTPRecipientsRefused([])

    with client as client:
        client.post("/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST)
        # a second attempt claims only a pending email; the first is counted while sending
        _wait_for(lambda: get_user_notices(db, TEST_USER_ID)[0].email_attempts > 1)


def test_email_is_retried_when_the_server_is_unreachable(
    client, outsider_jwt_cookie, db, smtp, mocker
):
    """Failing to connect to the mail server counts as an attempt, not a lost email"""
    mocker.patch.object(
        aiosmtplib.SMTP,
        "connect",
        new_callable=mocker.AsyncMock,
        side_effect=aiosmtplib.SMTPConnectError("no route to host"),
    )

    with client as client:
        client.post("/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST)
        _wait_for(lambda: get_user_notices(db, TEST_USER_ID)[0].email_attempts > 1)
        smtp.assert_not_awaited()


def test_sending_gives_up_at_the_retry_limit(client, outsider_jwt_cookie, db, smtp):
    """Retrying forever would make the outbox grow without bound"""
    smtp.side_effect = aiosmtplib.SMTPRecipientsRefused([])

    with client as client:
        client.post("/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST)
        _wait_for(
            lambda: (
                get_user_notices(db, TEST_USER_ID)[0].email_status == EmailStatus.FAILED
            )
        )

        assert get_user_notices(db, TEST_USER_ID)[0].email_attempts == (
            settings.CONFIG.notices.email_retry_limit
        )


def test_email_to_an_unknown_user_fails_at_once(client, db, smtp):
    """No address to send to means no retry will ever help"""
    notice = Notice(
        type="project-access-approved",
        title="Access approved",
        body="you are in",
        user_id=generate_id(),
        severity=NoticeSeverity.INFO,
        context={},
        email_status=EmailStatus.PENDING,
        email_attempts=0,
        created_at=get_current_timestamp(),
        updated_at=get_current_timestamp(),
    )
    db.insert(Notice, notice)

    with client as client:
        _wait_for(lambda: db.get(Notice, notice.id).email_status == EmailStatus.FAILED)

        smtp.assert_not_awaited()


def test_sweeper_survives_a_failing_sweep(
    client, outsider_jwt_cookie, db, smtp, mocker
):
    """One bad sweep must not stop the emailing for the rest of the process"""
    from services.notices import emails

    real_find = emails._find_notices_pending_email
    calls = []

    async def fail_once(database, limit: int):
        calls.append(limit)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return await real_find(database, limit)

    mocker.patch.object(emails, "_find_notices_pending_email", side_effect=fail_once)

    with client as client:
        client.post("/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST)
        _wait_for(
            lambda: (
                get_user_notices(db, TEST_USER_ID)[0].email_status == EmailStatus.SENT
            )
        )

        assert len(calls) > 1


def _wait_for(condition: Callable[[], bool], timeout: float = 10):
    """Polls the given condition until it holds

    Args:
        condition: the condition to wait for
        timeout: the seconds after which to give up

    Raises:
        TimeoutError: the condition did not hold within {timeout} seconds
    """
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError(f"the condition did not hold within {timeout} seconds")
        time.sleep(0.02)
