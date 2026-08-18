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

"""Tests for the /me/requests endpoints and personal projects"""
import pytest
from beanie import PydanticObjectId

from services.auth import Project
from services.auth.projects.dtos import personal_project_ext_id
from services.auth.user_requests import UserRequest
from tests._utils.auth import (
    TEST_NO_QPU_PROJECT_EXT_ID,
    TEST_OUTSIDER_EMAIL,
    TEST_OUTSIDER_ID,
    TEST_PROJECT_EXT_ID,
    TEST_PROJECT_ID,
    TEST_SUPERUSER_ID,
    TEST_USER_ID,
    get_db_record,
)
from utils import rate_limit

_ACCESS_URL = "/me/requests/"


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Rate limit counters outlive a test's database, so clear them explicitly"""
    yield
    for user_id in (TEST_OUTSIDER_ID, TEST_USER_ID, TEST_SUPERUSER_ID):
        rate_limit.reset(f"project-lookup:{user_id}")


def _request_access(client, cookie, ext_id=TEST_PROJECT_EXT_ID, reason="let me in"):
    return client.post(
        _ACCESS_URL,
        cookies=cookie,
        json={"type": "project-access", "project_ext_id": ext_id, "reason": reason},
    )


def test_request_project_access(client, outsider_jwt_cookie, db):
    """POST /me/requests/project-access creates a pending project-admin-scoped request"""
    with client as client:
        response = _request_access(client, outsider_jwt_cookie)
        got = response.json()

        assert response.status_code == 201
        assert got["type"] == "project-access"
        assert got["status"] == "pending"
        assert got["approver_scope"] == "project-admin"
        assert got["project_id"] == TEST_PROJECT_ID
        assert got["requester_id"] == TEST_OUTSIDER_ID
        assert got["request"]["project_name"] == "test-project"
        assert get_db_record(db, UserRequest, got["id"]) is not None


def test_request_access_to_unknown_project(client, outsider_jwt_cookie):
    """A project ext_id that does not exist is a 404"""
    with client as client:
        response = _request_access(
            client, outsider_jwt_cookie, ext_id="no-such-project"
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "no project with ID 'no-such-project'"}


def test_request_access_to_personal_project_is_not_found(
    client, outsider_jwt_cookie, db
):
    """Personal projects answer 404 identically, so they cannot be probed for"""
    ext_id = personal_project_ext_id(TEST_USER_ID)
    db["auth_projects"].insert_one(
        {
            "ext_id": ext_id,
            "name": "someone (personal)",
            "admin_id": TEST_USER_ID,
            "user_ids": [TEST_USER_ID],
            "qpu_seconds": 0,
            "is_personal": True,
        }
    )

    with client as client:
        response = _request_access(client, outsider_jwt_cookie, ext_id=ext_id)

        assert response.status_code == 404
        assert response.json() == {"detail": f"no project with ID '{ext_id}'"}


def test_request_access_when_already_a_member(client, user_jwt_cookie):
    """A member of the project gets 409 rather than a redundant request"""
    with client as client:
        response = _request_access(client, user_jwt_cookie)

        assert response.status_code == 409
        assert response.json() == {
            "detail": f"you are already a member of '{TEST_PROJECT_EXT_ID}'"
        }


def test_request_access_twice(client, outsider_jwt_cookie):
    """A second request for the same project while one is pending is a 409"""
    with client as client:
        assert _request_access(client, outsider_jwt_cookie).status_code == 201
        response = _request_access(client, outsider_jwt_cookie)

        assert response.status_code == 409
        assert response.json() == {
            "detail": f"a request for '{TEST_PROJECT_EXT_ID}' is already pending"
        }


def test_request_access_for_second_project(client, outsider_jwt_cookie):
    """A pending request for one project does not block a request for another"""
    with client as client:
        assert _request_access(client, outsider_jwt_cookie).status_code == 201
        response = _request_access(
            client, outsider_jwt_cookie, ext_id=TEST_NO_QPU_PROJECT_EXT_ID
        )

        assert response.status_code == 201


def test_failed_lookups_are_rate_limited(client, outsider_jwt_cookie):
    """Repeated failed lookups eventually 429, so ext_ids cannot be enumerated"""
    limit = 20
    with client as client:
        for attempt in range(limit):
            response = _request_access(
                client, outsider_jwt_cookie, ext_id=f"nope-{attempt}"
            )
            assert response.status_code == 404

        response = _request_access(client, outsider_jwt_cookie, ext_id="nope-last")

        assert response.status_code == 429
        assert "rate limit exceeded" in response.json()["detail"]


def test_rate_limit_is_checked_before_the_lookup(client, outsider_jwt_cookie):
    """Once limited, even a real project returns 429 and reveals nothing"""
    with client as client:
        for attempt in range(20):
            _request_access(client, outsider_jwt_cookie, ext_id=f"nope-{attempt}")

        response = _request_access(client, outsider_jwt_cookie)

        assert response.status_code == 429


def test_successful_lookups_are_not_counted(client, outsider_jwt_cookie):
    """Only failures count against the limit"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        assert (
            rate_limit.get_connection().get(
                "__ratelimit__project-lookup:" + TEST_OUTSIDER_ID
            )
            is None
        )


def test_pending_request_quota(client, outsider_jwt_cookie, db, inserted_projects):
    """A user may not hold more than the configured number of pending requests"""
    extra = [
        {
            "type": "project-qpu-seconds",
            "requester_id": TEST_OUTSIDER_ID,
            "status": "pending",
            "request": {},
        }
        for _ in range(5)
    ]
    db["auth_user_requests"].insert_many(extra)

    with client as client:
        response = _request_access(client, outsider_jwt_cookie)

        assert response.status_code == 429
        assert response.json() == {
            "detail": "too many pending requests; at most 5 allowed"
        }


def test_unauthenticated_request_access(client):
    """Requesting access without a cookie is a 401"""
    with client as client:
        response = client.post(
            _ACCESS_URL,
            json={
                "type": "project-access",
                "project_ext_id": TEST_PROJECT_EXT_ID,
                "reason": "hi",
            },
        )

        assert response.status_code == 401


def test_view_my_requests(client, outsider_jwt_cookie):
    """GET /me/requests/ returns the requests the current user made"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)
        response = client.get("/me/requests/", cookies=outsider_jwt_cookie)

        got = response.json()
        assert response.status_code == 200
        assert got["skip"] == 0
        assert [item["requester_id"] for item in got["data"]] == [TEST_OUTSIDER_ID]


def test_my_requests_exclude_other_users(client, outsider_jwt_cookie, user_jwt_cookie):
    """A user sees only their own requests as requester"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)
        response = client.get("/me/requests/", cookies=user_jwt_cookie)

        assert response.json()["data"] == []


def test_view_requests_as_approver(client, outsider_jwt_cookie, user_jwt_cookie):
    """A project admin sees requests for the projects they administer"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)
        response = client.get(
            "/me/requests/?role=approver&status=pending", cookies=user_jwt_cookie
        )

        got = response.json()
        assert response.status_code == 200
        assert [item["project_id"] for item in got["data"]] == [TEST_PROJECT_ID]


def test_approver_view_excludes_qpu_requests(client, user_jwt_cookie, db):
    """System-admin-scoped requests never appear in a project admin's queue"""
    db["auth_user_requests"].insert_one(
        {
            "type": "project-qpu-seconds",
            "requester_id": TEST_OUTSIDER_ID,
            "status": "pending",
            "approver_scope": "system-admin",
            "project_id": TEST_PROJECT_ID,
            "request": {"project_id": TEST_PROJECT_ID, "seconds": 10, "reason": "x"},
        }
    )

    with client as client:
        response = client.get("/me/requests/?role=approver", cookies=user_jwt_cookie)

        assert response.status_code == 200
        assert response.json()["data"] == []


def test_superuser_sees_all_requests_as_approver(
    client, outsider_jwt_cookie, admin_jwt_cookie
):
    """A superuser is an eligible approver for everything"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)
        response = client.get("/me/requests/?role=approver", cookies=admin_jwt_cookie)

        assert response.status_code == 200
        assert len(response.json()["data"]) == 1


def test_approve_project_access(client, outsider_jwt_cookie, user_jwt_cookie, db):
    """The project admin approving adds the requester to the project"""
    with client as client:
        request_id = _request_access(client, outsider_jwt_cookie).json()["id"]

        response = client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        got = response.json()
        assert response.status_code == 200
        assert got["status"] == "approved"
        assert got["approver_id"] == TEST_USER_ID

        project = get_db_record(db, Project, TEST_PROJECT_ID)
        assert TEST_OUTSIDER_ID in project["user_ids"]
        assert TEST_OUTSIDER_EMAIL in project["user_emails"]


def test_approve_is_idempotent_on_membership(
    client, outsider_jwt_cookie, user_jwt_cookie, db
):
    """The membership update uses $addToSet, so a duplicate cannot appear"""
    with client as client:
        request_id = _request_access(client, outsider_jwt_cookie).json()["id"]
        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        project = get_db_record(db, Project, TEST_PROJECT_ID)
        assert project["user_ids"].count(TEST_OUTSIDER_ID) == 1


def test_reject_project_access(client, outsider_jwt_cookie, user_jwt_cookie, db):
    """Rejecting records the reason and leaves membership untouched"""
    with client as client:
        request_id = _request_access(client, outsider_jwt_cookie).json()["id"]

        response = client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "rejected", "rejection_reason": "not on this project"},
        )

        got = response.json()
        assert response.status_code == 200
        assert got["status"] == "rejected"
        assert got["rejection_reason"] == "not on this project"

        project = get_db_record(db, Project, TEST_PROJECT_ID)
        assert TEST_OUTSIDER_ID not in project["user_ids"]


def test_react_twice_is_a_conflict(client, outsider_jwt_cookie, user_jwt_cookie):
    """A decided request cannot be decided again"""
    with client as client:
        request_id = _request_access(client, outsider_jwt_cookie).json()["id"]
        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        response = client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "rejected"},
        )

        assert response.status_code == 409
        assert response.json() == {"detail": "request has already been approved"}


def test_react_when_not_the_project_admin(client, outsider_jwt_cookie):
    """A user who administers nothing cannot react, not even to their own request"""
    with client as client:
        request_id = _request_access(client, outsider_jwt_cookie).json()["id"]

        response = client.put(
            f"/me/requests/{request_id}",
            cookies=outsider_jwt_cookie,
            json={"status": "approved"},
        )

        assert response.status_code == 403
        assert response.json() == {
            "detail": "you are not entitled to react to this request"
        }


def test_superuser_can_react(client, outsider_jwt_cookie, admin_jwt_cookie, db):
    """A superuser may react to a project-admin-scoped request"""
    with client as client:
        request_id = _request_access(client, outsider_jwt_cookie).json()["id"]

        response = client.put(
            f"/me/requests/{request_id}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )

        assert response.status_code == 200
        assert response.json()["approver_id"] == TEST_SUPERUSER_ID


def test_react_to_unknown_request(client, user_jwt_cookie):
    """Reacting to a request that does not exist is a 404"""
    unknown_id = PydanticObjectId()
    with client as client:
        response = client.put(
            f"/me/requests/{unknown_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        assert response.status_code == 404


def test_non_superuser_cannot_grant_qpu_seconds_on_own_personal_project(
    client, outsider_jwt_cookie, db
):
    """QPU seconds stay a system-admin allocation even on a self-administered project"""
    ext_id = personal_project_ext_id(TEST_OUTSIDER_ID)
    project_id = PydanticObjectId()
    db["auth_projects"].insert_one(
        {
            "_id": project_id,
            "ext_id": ext_id,
            "name": "someone (personal)",
            "admin_id": TEST_OUTSIDER_ID,
            "user_ids": [TEST_OUTSIDER_ID],
            "qpu_seconds": 0,
            "is_personal": True,
        }
    )
    request_id = PydanticObjectId()
    db["auth_user_requests"].insert_one(
        {
            "_id": request_id,
            "type": "project-qpu-seconds",
            "requester_id": TEST_OUTSIDER_ID,
            "status": "pending",
            "approver_scope": "system-admin",
            "project_id": str(project_id),
            "request": {
                "project_id": str(project_id),
                "seconds": 5000,
                "reason": "more please",
            },
        }
    )

    with client as client:
        response = client.put(
            f"/me/requests/{request_id}",
            cookies=outsider_jwt_cookie,
            json={"status": "approved"},
        )

        assert response.status_code == 403
        project = get_db_record(db, Project, str(project_id))
        assert project["qpu_seconds"] == 0


def test_superuser_grants_qpu_seconds(client, admin_jwt_cookie, db):
    """Approving a QPU request increments the project and clears the low-QPU latch"""
    request_id = PydanticObjectId()
    db["auth_projects"].update_one(
        {"ext_id": TEST_PROJECT_EXT_ID},
        {"$set": {"qpu_seconds": 10, "low_qpu_notified_at": "2026-01-01T00:00:00Z"}},
    )
    db["auth_user_requests"].insert_one(
        {
            "_id": request_id,
            "type": "project-qpu-seconds",
            "requester_id": TEST_USER_ID,
            "status": "pending",
            "approver_scope": "system-admin",
            "project_id": TEST_PROJECT_ID,
            "request": {
                "project_id": TEST_PROJECT_ID,
                "seconds": 90,
                "reason": "more please",
            },
        }
    )

    with client as client:
        response = client.put(
            f"/me/requests/{request_id}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )

        assert response.status_code == 200
        project = get_db_record(db, Project, TEST_PROJECT_ID)
        assert project["qpu_seconds"] == 100
        assert project["low_qpu_notified_at"] is None
