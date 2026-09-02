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

"""Tests for bulk QPU-second grants to personal projects"""
import pytest
from beanie import PydanticObjectId

import settings
from services.auth import Project
from services.auth.projects.dtos import personal_project_ext_id, personal_project_name
from services.notifications import NotificationType
from tests._utils.auth import (
    TEST_OUTSIDER_EMAIL,
    TEST_OUTSIDER_ID,
    TEST_PROJECT_ID,
    TEST_SUPERUSER_EMAIL,
    TEST_USER_EMAIL,
    TEST_USER_ID,
    get_db_record,
)

_URL = "/admin/qpu-seconds-grants/"
_GRANT_COLLECTION = "qpu_seconds_grants"


@pytest.fixture
def personal_projects(db):
    """Personal projects for the plain user and the outsider, as login would create"""
    records = [
        {
            "_id": PydanticObjectId(),
            "ext_id": personal_project_ext_id(user_id),
            "name": personal_project_name(email),
            "admin_id": user_id,
            "user_ids": [user_id],
            "user_emails": [email],
            "qpu_seconds": 100,
            "is_active": True,
            "is_personal": True,
        }
        for user_id, email in (
            (TEST_USER_ID, TEST_USER_EMAIL),
            (TEST_OUTSIDER_ID, TEST_OUTSIDER_EMAIL),
        )
    ]
    db["auth_projects"].insert_many(records)
    yield records


def _grant(client, cookie, key="key-1", **overrides):
    body = {
        "seconds": 3600,
        "target": "emails",
        "target_emails": [TEST_USER_EMAIL],
        "reason": "new QPU online",
    }
    body.update(overrides)
    return client.post(
        _URL, cookies=cookie, json=body, headers={"Idempotency-Key": key}
    )


def test_grant_by_email(client, admin_jwt_cookie, db, personal_projects):
    """Granting by email tops up exactly the named users' personal projects"""
    with client as client:
        response = _grant(client, admin_jwt_cookie)

        got = response.json()
        assert response.status_code == 201
        assert got == {"seconds": 3600, "granted": 1, "skipped": []}

        target = get_db_record(
            db, Project, _filter={"ext_id": personal_project_ext_id(TEST_USER_ID)}
        )
        other = get_db_record(
            db, Project, _filter={"ext_id": personal_project_ext_id(TEST_OUTSIDER_ID)}
        )
        assert target["qpu_seconds"] == 3700
        assert other["qpu_seconds"] == 100


def test_grant_to_all_personal_projects(
    client, admin_jwt_cookie, db, personal_projects
):
    """The all-personal-projects target reaches every existing personal project"""
    with client as client:
        response = _grant(
            client, admin_jwt_cookie, target="all-personal-projects", target_emails=None
        )

        assert response.status_code == 201
        assert response.json()["granted"] == 2
        for user_id in (TEST_USER_ID, TEST_OUTSIDER_ID):
            record = get_db_record(
                db, Project, _filter={"ext_id": personal_project_ext_id(user_id)}
            )
            assert record["qpu_seconds"] == 3700


def test_shared_projects_are_untouched(client, admin_jwt_cookie, db, personal_projects):
    """A grant never touches shared projects, even in all-personal-projects mode"""
    before = get_db_record(db, Project, TEST_PROJECT_ID)["qpu_seconds"]

    with client as client:
        _grant(
            client, admin_jwt_cookie, target="all-personal-projects", target_emails=None
        )

        assert get_db_record(db, Project, TEST_PROJECT_ID)["qpu_seconds"] == before


def test_replayed_grant_is_a_no_op(client, admin_jwt_cookie, db, personal_projects):
    """The same idempotency key grants once, however many times it is sent"""
    with client as client:
        first = _grant(client, admin_jwt_cookie, key="replay-me")
        second = _grant(client, admin_jwt_cookie, key="replay-me")

        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json() == first.json()

        record = get_db_record(
            db, Project, _filter={"ext_id": personal_project_ext_id(TEST_USER_ID)}
        )
        assert record["qpu_seconds"] == 3700
        assert db[_GRANT_COLLECTION].count_documents({}) == 1


def test_distinct_keys_grant_twice(client, admin_jwt_cookie, db, personal_projects):
    """A deliberate second grant is a distinct operation, not a replay"""
    with client as client:
        _grant(client, admin_jwt_cookie, key="first")
        _grant(client, admin_jwt_cookie, key="second")

        record = get_db_record(
            db, Project, _filter={"ext_id": personal_project_ext_id(TEST_USER_ID)}
        )
        assert record["qpu_seconds"] == 7300
        assert db[_GRANT_COLLECTION].count_documents({}) == 2


def test_dormant_user_is_skipped_not_provisioned(
    client, admin_jwt_cookie, db, personal_projects
):
    """A user who never logged in has no personal project, and none is created for them"""
    with client as client:
        response = _grant(
            client,
            admin_jwt_cookie,
            target_emails=[TEST_USER_EMAIL, TEST_SUPERUSER_EMAIL],
        )

        got = response.json()
        assert response.status_code == 201
        assert got["granted"] == 1
        assert got["skipped"] == [
            {
                "email": TEST_SUPERUSER_EMAIL,
                "why": "no personal project yet — user has never logged in",
            }
        ]
        assert db["auth_projects"].count_documents({"is_personal": True}) == 2


def test_unknown_email_is_reported(client, admin_jwt_cookie, personal_projects):
    """A mistyped address is reported rather than silently ignored"""
    with client as client:
        response = _grant(client, admin_jwt_cookie, target_emails=["typo@example.com"])

        got = response.json()
        assert got["granted"] == 0
        assert got["skipped"] == [{"email": "typo@example.com", "why": "no such user"}]


def test_grant_clears_the_low_qpu_latch(
    client, admin_jwt_cookie, db, personal_projects
):
    """A topped-up project warns again next time it runs low"""
    db["auth_projects"].update_one(
        {"ext_id": personal_project_ext_id(TEST_USER_ID)},
        {"$set": {"low_qpu_notified_at": "2026-01-01T00:00:00Z"}},
    )

    with client as client:
        _grant(client, admin_jwt_cookie)

        record = get_db_record(
            db, Project, _filter={"ext_id": personal_project_ext_id(TEST_USER_ID)}
        )
        assert record["low_qpu_notified_at"] is None


def test_grant_notifies_the_owner(client, admin_jwt_cookie, db, personal_projects):
    """The owner is told how much they got"""
    with client as client:
        _grant(client, admin_jwt_cookie)

        got = list(db["notices"].find({"user_id": PydanticObjectId(TEST_USER_ID)}))

        assert [item["type"] for item in got] == [NotificationType.QPU_SECONDS_GRANTED]
        assert got[0]["context"]["reason"] == "admin-grant"
        assert "3600s" in got[0]["title"]


def test_grant_above_the_cap_is_refused(
    client, admin_jwt_cookie, db, personal_projects
):
    """A mistyped figure cannot hand out a decade of machine time"""
    with client as client:
        response = _grant(
            client,
            admin_jwt_cookie,
            seconds=settings.CONFIG.projects.max_grant_seconds + 1,
        )

        assert response.status_code == 403
        assert "may not exceed" in response.json()["detail"]
        record = get_db_record(
            db, Project, _filter={"ext_id": personal_project_ext_id(TEST_USER_ID)}
        )
        assert record["qpu_seconds"] == 100


def test_grant_requires_a_positive_figure(client, admin_jwt_cookie):
    """Zero or negative seconds is a validation error, not a silent no-op"""
    with client as client:
        response = _grant(client, admin_jwt_cookie, seconds=0)

        assert response.status_code == 422


def test_email_target_requires_emails(client, admin_jwt_cookie):
    """An email-targeted grant with no emails would affect nobody, so it is refused"""
    with client as client:
        response = _grant(client, admin_jwt_cookie, target_emails=None)

        assert response.status_code == 422


def test_grant_requires_an_idempotency_key(client, admin_jwt_cookie):
    """The key is what makes a replay safe, so it is mandatory"""
    with client as client:
        response = client.post(
            _URL,
            cookies=admin_jwt_cookie,
            json={
                "seconds": 60,
                "target": "all-personal-projects",
                "reason": "x",
            },
        )

        assert response.status_code == 422


def test_non_superuser_cannot_grant(client, user_jwt_cookie, db, personal_projects):
    """Granting QPU time stays a system-admin power"""
    with client as client:
        response = _grant(client, user_jwt_cookie)

        assert response.status_code == 403
        record = get_db_record(
            db, Project, _filter={"ext_id": personal_project_ext_id(TEST_USER_ID)}
        )
        assert record["qpu_seconds"] == 100


def test_concurrent_replay_grants_once(
    client, admin_jwt_cookie, db, personal_projects, mocker
):
    """A grant losing the insert race returns the winner's report rather than erroring

    Simulated by making the pre-flight lookup miss once, so the insert hits the unique
    index on idempotency_key exactly as the loser of a real race would.
    """
    from services.qpu_grants import service as grant_service

    real_find_one = grant_service.QpuSecondsGrant.find_one
    calls = {"n": 0}

    def miss_once(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:

            async def none():
                return None

            return none()
        return real_find_one(*args, **kwargs)

    with client as client:
        first = _grant(client, admin_jwt_cookie, key="racer")
        mocker.patch.object(
            grant_service.QpuSecondsGrant, "find_one", side_effect=miss_once
        )

        second = _grant(client, admin_jwt_cookie, key="racer")

        assert second.status_code == 201
        assert second.json() == first.json()
        record = get_db_record(
            db, Project, _filter={"ext_id": personal_project_ext_id(TEST_USER_ID)}
        )
        assert record["qpu_seconds"] == 3700
        assert db[_GRANT_COLLECTION].count_documents({}) == 1


def test_view_grant_history(client, admin_jwt_cookie, personal_projects):
    """GET returns the grants made, newest first"""
    with client as client:
        _grant(client, admin_jwt_cookie, key="one", reason="first grant")
        _grant(client, admin_jwt_cookie, key="two", reason="second grant")

        response = client.get(_URL, cookies=admin_jwt_cookie)

        got = response.json()
        assert response.status_code == 200
        assert [item["reason"] for item in got["data"]] == [
            "second grant",
            "first grant",
        ]


def test_non_superuser_cannot_view_history(client, user_jwt_cookie):
    """The audit trail is superuser-only"""
    with client as client:
        assert client.get(_URL, cookies=user_jwt_cookie).status_code == 403
