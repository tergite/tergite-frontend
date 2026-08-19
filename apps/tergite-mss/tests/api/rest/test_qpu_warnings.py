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

"""Tests for the low and depleted QPU-second warnings raised by job usage

Rearming the latch on a grant is covered where the granting lives, in test_requests.py
and test_qpu_grants.py.
"""
import uuid
from datetime import datetime

import pytest
from beanie import PydanticObjectId

import settings
from services.auth import Project
from services.notifications import NotificationType
from tests._utils.auth import (
    TEST_PROJECT_EXT_ID,
    TEST_PROJECT_ID,
    TEST_SYSTEM_USER_ID,
    TEST_USER_ID,
    get_db_record,
)
from tests._utils.bcc import create_bcc_headers
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import insert_in_collection
from tests._utils.records import (
    with_current_timestamps,
    with_incremental_timestamps,
)

_JOBS_LIST = load_json_fixture("job_list.json")
_JOBS_COLLECTION = "jobs"
_PROJECTS_COLLECTION = "auth_projects"
_NOTIFICATIONS_COLLECTION = "notifications"
_DEVICE = "Loke"
# one payload with execution timestamps is enough; the billing itself is tested elsewhere
_JOB_UPDATE = load_json_fixture("job_timestamped_updates.json")[0]
_EXECUTION = _JOB_UPDATE["timestamps"]["execution"]
# unrounded: the service bills the exact duration, and the balance assertion compares to it
_JOB_COST = (
    datetime.fromisoformat(_EXECUTION["finished"].replace("Z", "+00:00"))
    - datetime.fromisoformat(_EXECUTION["started"].replace("Z", "+00:00"))
).total_seconds()


# derived from the job cost rather than hardcoded, so a changed fixture cannot silently
# turn a "drops below the threshold" case into a "runs out entirely" one
_THRESHOLD = _JOB_COST * 2


@pytest.fixture
def threshold():
    """A threshold one job cannot clear on its own, so low and depleted stay distinct"""
    original = settings.CONFIG.projects.qpu_seconds_low_threshold
    settings.CONFIG.projects.qpu_seconds_low_threshold = _THRESHOLD
    yield _THRESHOLD
    settings.CONFIG.projects.qpu_seconds_low_threshold = original


def _bill_a_job(client, db, starting_seconds=None):
    """Runs one job against the test project, optionally setting its balance first

    Args:
        client: the test client
        db: the mongo database
        starting_seconds: the balance to start from; None leaves it and the latch as they are
    """
    raw_jobs = with_incremental_timestamps(
        _JOBS_LIST, fields=["created_at", "calibration_date"]
    )
    raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])
    insert_in_collection(
        database=db,
        collection_name=_JOBS_COLLECTION,
        data=[{**item, "project_id": str(TEST_PROJECT_ID)} for item in raw_jobs],
    )
    if starting_seconds is not None:
        db[_PROJECTS_COLLECTION].update_one(
            {"ext_id": TEST_PROJECT_EXT_ID},
            {"$set": {"qpu_seconds": starting_seconds, "low_qpu_notified_at": None}},
        )

    with client as client:
        with client.websocket_connect(
            f"/devices/ws/{_DEVICE}", headers=create_bcc_headers(_DEVICE)
        ) as socket:
            socket.send_json(
                {"id": str(uuid.uuid4()), "name": "job_updated", "data": _JOB_UPDATE}
            )
            assert socket.receive_json()["status"] == "success"


def _notifications_of(db, type_: NotificationType):
    return list(db[_NOTIFICATIONS_COLLECTION].find({"type": type_}))


def _project(db):
    return get_db_record(db, schema=Project, _filter={"ext_id": TEST_PROJECT_EXT_ID})


def test_spending_still_tracks_the_running_balance(client, db, threshold):
    """Gating the latch on the sign must not gate the decrement itself

    The warning is decided from the balance the decrement returns, so a spend that failed to
    apply would leave a project that never warns and never runs out.
    """
    start = threshold + _JOB_COST - 1

    _bill_a_job(client, db, starting_seconds=start)

    assert _project(db)["qpu_seconds"] == pytest.approx(start - _JOB_COST)


def test_dropping_below_the_threshold_warns_the_admin(client, db, threshold):
    """The person who can request more time is the one told about it"""
    _bill_a_job(client, db, starting_seconds=threshold + _JOB_COST - 1)

    got = _notifications_of(db, NotificationType.QPU_SECONDS_LOW)

    assert len(got) == 1
    assert f"{threshold + _JOB_COST - 1 - _JOB_COST:.0f}s" in got[0]["body"]
    assert got[0]["user_id"] == PydanticObjectId(TEST_USER_ID)
    assert "test-project" in got[0]["title"]
    assert got[0]["severity"] == "warning"
    assert _project(db)["low_qpu_notified_at"] is not None


def test_staying_above_the_threshold_warns_nobody(client, db, threshold):
    """A project with plenty of time left is not worth interrupting anyone over"""
    _bill_a_job(client, db, starting_seconds=threshold * 10)

    assert _notifications_of(db, NotificationType.QPU_SECONDS_LOW) == []
    assert _project(db)["low_qpu_notified_at"] is None


def test_a_second_job_does_not_warn_again(client, db, threshold):
    """The regression guard: spending must not clear the latch, or every job warns"""
    _bill_a_job(client, db, starting_seconds=threshold + _JOB_COST - 1)
    latch = _project(db)["low_qpu_notified_at"]
    db[_JOBS_COLLECTION].delete_many({})

    _bill_a_job(client, db)

    assert len(_notifications_of(db, NotificationType.QPU_SECONDS_LOW)) == 1
    assert _project(db)["low_qpu_notified_at"] == latch


def test_running_out_tells_the_admin_and_the_members(client, db, threshold):
    """Members cannot fix it but they need to know why their jobs stopped"""
    _bill_a_job(client, db, starting_seconds=1)

    got = _notifications_of(db, NotificationType.QPU_SECONDS_DEPLETED)

    assert {record["user_id"] for record in got} == {
        PydanticObjectId(TEST_USER_ID),
        PydanticObjectId(TEST_SYSTEM_USER_ID),
    }
    assert all(record["severity"] == "critical" for record in got)
    assert _project(db)["low_qpu_notified_at"] is not None


def test_running_out_reports_even_after_a_low_warning(client, db, threshold):
    """Depletion is judged on the crossing, so a stamped latch must not swallow it"""
    _bill_a_job(client, db, starting_seconds=threshold + _JOB_COST - 1)
    assert len(_notifications_of(db, NotificationType.QPU_SECONDS_LOW)) == 1
    db[_JOBS_COLLECTION].delete_many({})
    db[_PROJECTS_COLLECTION].update_one(
        {"ext_id": TEST_PROJECT_EXT_ID}, {"$set": {"qpu_seconds": 1}}
    )

    _bill_a_job(client, db)

    assert len(_notifications_of(db, NotificationType.QPU_SECONDS_DEPLETED)) == 2


def test_an_already_empty_project_does_not_warn_again(client, db, threshold):
    """Only the job that crosses zero reports it"""
    _bill_a_job(client, db, starting_seconds=-5)

    assert _notifications_of(db, NotificationType.QPU_SECONDS_DEPLETED) == []


def test_the_warnings_are_silenceable(client, db, threshold, user_jwt_cookie):
    """Nothing awaits the reader's action here, so the policy allows opting out"""
    with client as client:
        response = client.put(
            "/me/notification-preferences/",
            cookies=user_jwt_cookie,
            json={"qpu-seconds-low": {"in_app": False, "email": False}},
        )

    assert response.json()["qpu-seconds-low"]["in_app"] is False

    _bill_a_job(client, db, starting_seconds=threshold + _JOB_COST - 1)

    assert _notifications_of(db, NotificationType.QPU_SECONDS_LOW) == []
