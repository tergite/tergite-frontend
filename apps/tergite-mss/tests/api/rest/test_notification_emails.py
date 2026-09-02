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

"""Tests for the email channel: queueing, the outbox sweeper and the SMTP client"""
import asyncio
import time
from typing import Callable

import aiosmtplib
import pytest
from beanie import PydanticObjectId

import settings
from services.external import email
from services.notifications import CHANNEL_POLICY, EmailStatus, NotificationType
from services.notifications.templates import render_email
from tests._utils.auth import TEST_PROJECT_EXT_ID, TEST_USER_EMAIL, TEST_USER_ID
from tests._utils.env import TEST_APP_CONFIG
from utils import rate_limit
from utils.config import AppConfig, EmailConfig
from utils.date_time import get_current_timestamp
from utils.exc import ServiceUnavailableError

_COLLECTION = "notices"
_DASHBOARD_URL = "https://dashboard.example.com"
_TEST_EMAIL_CONFIG = EmailConfig(
    host="smtp.example.com",
    port=2525,
    username="mss@example.com",
    password="hidden",
    from_address="no-reply@example.com",
    from_name="Tergite Test",
)


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Rate limit counters outlive a test's database, so clear them explicitly"""
    yield
    rate_limit.reset(f"project-lookup:{TEST_USER_ID}")


@pytest.fixture
def email_configured():
    """Turns on the email channel for the duration of the test"""
    original_email = settings.CONFIG.email
    original_url = settings.CONFIG.notices.dashboard_url
    settings.CONFIG.email = _TEST_EMAIL_CONFIG
    settings.CONFIG.notices.dashboard_url = _DASHBOARD_URL
    yield _TEST_EMAIL_CONFIG
    settings.CONFIG.email = original_email
    settings.CONFIG.notices.dashboard_url = original_url


@pytest.fixture
def fast_sweeps():
    """Sweeps often enough that a test need not wait a whole interval"""
    original = settings.CONFIG.notices.email_sweep_interval
    settings.CONFIG.notices.email_sweep_interval = 0.05
    yield
    settings.CONFIG.notices.email_sweep_interval = original


@pytest.fixture
def sweeper_disabled(mocker):
    """Keeps the outbox untouched, so queueing can be asserted on its own"""
    yield mocker.patch("services.notices.start_sweeper")


@pytest.fixture
def smtp(mocker):
    """Captures the messages handed to aiosmtplib instead of sending them"""
    yield mocker.patch(
        "services.external.email.service.aiosmtplib.send",
        new_callable=mocker.AsyncMock,
    )


@pytest.fixture
def failing_smtp(mocker):
    """An SMTP server that refuses everything"""
    yield mocker.patch(
        "services.external.email.service.aiosmtplib.send",
        new_callable=mocker.AsyncMock,
        side_effect=aiosmtplib.SMTPConnectError("no route to host"),
    )


def _request_access(client, cookie):
    return client.post(
        "/me/requests/",
        cookies=cookie,
        json={
            "type": "project-access",
            "project_ext_id": TEST_PROJECT_EXT_ID,
            "reason": "let me in",
        },
    )


def _notification_for(db, user_id):
    return db[_COLLECTION].find_one({"user_id": PydanticObjectId(user_id)})


def _wait_until(predicate: Callable[[], bool], timeout: float = 5) -> bool:
    """Waits for the sweeper, which runs on the test client's own event loop thread"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_email_is_queued_when_configured(
    client, outsider_jwt_cookie, db, email_configured, sweeper_disabled
):
    """A configured channel makes the notification row its own outbox entry"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        assert _notification_for(db, TEST_USER_ID)["email_status"] == (
            EmailStatus.PENDING
        )


def test_email_is_not_queued_when_unconfigured(client, outsider_jwt_cookie, db):
    """Without SMTP nothing is ever queued, so the sweeper has nothing to find"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        assert _notification_for(db, TEST_USER_ID)["email_status"] == (
            EmailStatus.NOT_APPLICABLE
        )


def test_email_is_not_queued_when_opted_out(
    client, outsider_jwt_cookie, user_jwt_cookie, db, email_configured, sweeper_disabled
):
    """An opt-out is honoured at write time, so no mail is ever queued"""
    with client as client:
        client.put(
            "/me/notification-preferences/",
            cookies=user_jwt_cookie,
            json={"project-access-requested": {"in_app": True, "email": False}},
        )

        _request_access(client, outsider_jwt_cookie)

        assert _notification_for(db, TEST_USER_ID)["email_status"] == (
            EmailStatus.NOT_APPLICABLE
        )


def test_sweeper_sends_a_queued_email(
    client, outsider_jwt_cookie, db, email_configured, fast_sweeps, smtp
):
    """The end-to-end path: a request notifies an admin, who is then emailed"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        assert _wait_until(
            lambda: _notification_for(db, TEST_USER_ID)["email_status"]
            == EmailStatus.SENT
        )

    message = smtp.call_args.args[0]
    assert message["To"] == TEST_USER_EMAIL
    assert message["From"] == "Tergite Test <no-reply@example.com>"
    assert "test-project" in message["Subject"]
    assert _DASHBOARD_URL in message.get_content()
    assert _notification_for(db, TEST_USER_ID)["email_attempts"] == 1


def test_a_failed_send_stays_pending(
    client, outsider_jwt_cookie, db, email_configured, fast_sweeps, failing_smtp
):
    """A dead mail server must not lose the mail"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        assert _wait_until(
            lambda: _notification_for(db, TEST_USER_ID)["email_attempts"] > 0
        )

        assert _notification_for(db, TEST_USER_ID)["email_status"] == (
            EmailStatus.PENDING
        )


def test_sending_gives_up_at_the_retry_limit(
    client, outsider_jwt_cookie, db, email_configured, fast_sweeps, failing_smtp
):
    """Retrying forever would make the outbox grow without bound"""
    retry_limit = settings.CONFIG.notices.email_retry_limit

    with client as client:
        _request_access(client, outsider_jwt_cookie)

        assert _wait_until(
            lambda: _notification_for(db, TEST_USER_ID)["email_status"]
            == EmailStatus.FAILED
        )

        assert _notification_for(db, TEST_USER_ID)["email_attempts"] == retry_limit


def test_a_notification_for_an_unknown_user_fails_at_once(
    client, db, email_configured, fast_sweeps, smtp
):
    """No address to send to means no retry will ever help"""
    db[_COLLECTION].insert_one(_orphan_notification())

    with client as client:
        assert _wait_until(
            lambda: db[_COLLECTION].find_one({})["email_status"] == EmailStatus.FAILED
        )

        smtp.assert_not_awaited()


def test_sweeper_does_not_run_when_unconfigured(
    client, outsider_jwt_cookie, db, fast_sweeps, smtp
):
    """An unconfigured channel starts no background task"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)
        time.sleep(0.2)

        smtp.assert_not_awaited()


def test_sweeper_survives_a_failing_sweep(
    client, db, email_configured, fast_sweeps, mocker
):
    """One bad sweep must not take the loop down for the rest of the process"""
    sweep = mocker.patch(
        "services.notices.outbox.send_pending",
        new_callable=mocker.AsyncMock,
        side_effect=[RuntimeError("boom"), 0, 0, 0, 0, 0, 0, 0, 0, 0],
    )

    with client as client:
        assert _wait_until(lambda: sweep.await_count > 1)


def test_send_without_configuration_is_rejected():
    """The client refuses rather than silently dropping the message"""
    with pytest.raises(ServiceUnavailableError, match="not configured"):
        _run(email._send_email("someone@example.com", "hi", "there"))


def test_send_passes_the_smtp_settings_through(smtp):
    """The transport is driven entirely by config, including STARTTLS"""
    _run(
        email._send_email("someone@example.com", "hi", "there", conf=_TEST_EMAIL_CONFIG)
    )

    assert smtp.await_args.kwargs == {
        "hostname": "smtp.example.com",
        "port": 2525,
        "username": "mss@example.com",
        "password": "hidden",
        "start_tls": True,
        "timeout": 10,
    }


def test_email_body_links_to_the_dashboard():
    """The mail is a nudge; the dashboard is where anything can be done about it"""
    got = render_email("Access requested", "alice wants in", "https://dash.example/")

    assert got.splitlines()[0] == "Access requested"
    assert "alice wants in" in got
    assert "https://dash.example" in got
    assert "https://dash.example/" not in got


def test_email_body_omits_a_link_when_no_url_is_set():
    """Config makes dashboard_url mandatory with SMTP, but render must not assume it"""
    got = render_email("Access requested", "alice wants in", None)

    assert "See it in the dashboard" not in got


def test_email_config_requires_a_dashboard_url():
    """Silently sending mail with dead links is worse than failing at startup"""
    with pytest.raises(ValueError, match="dashboard_url is required"):
        AppConfig(**{**TEST_APP_CONFIG, "email": _TEST_EMAIL_CONFIG.model_dump()})


def test_email_config_accepts_a_dashboard_url():
    """The same config is valid once the deep links have somewhere to point"""
    got = AppConfig(
        **{
            **TEST_APP_CONFIG,
            "email": _TEST_EMAIL_CONFIG.model_dump(),
            "notices": {"dashboard_url": _DASHBOARD_URL},
        }
    )

    assert got.email.host == "smtp.example.com"


def test_every_notification_type_declares_an_email_default():
    """A type missing from the policy would raise on notify rather than skip the email"""
    assert set(CHANNEL_POLICY) == set(NotificationType)


def _orphan_notification() -> dict:
    """A queued notification whose recipient no longer exists"""
    return {
        "user_id": PydanticObjectId(),
        "type": NotificationType.PROJECT_ACCESS_APPROVED,
        "title": "Access approved",
        "body": "you are in",
        "severity": "info",
        "context": {},
        "email_status": EmailStatus.PENDING,
        "email_attempts": 0,
        "created_at": get_current_timestamp(),
        "updated_at": get_current_timestamp(),
    }


def _run(coroutine):
    """Drives one coroutine that needs no database of its own"""
    return asyncio.run(coroutine)
