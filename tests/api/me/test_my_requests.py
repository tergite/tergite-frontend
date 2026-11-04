# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2024, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Integration tests for the /me/requests routes"""

import pytest

from libs.storage import generate_id
from services.auth import DeletedProject, Project, User
from services.notices import NoticeTypeId
from services.requests import Request
from tests._utils.auth import (
    TEST_OUTSIDER_EMAIL,
    TEST_OUTSIDER_ID,
    TEST_PROJECT_ID,
    TEST_PROJECT_NAME,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_EMAIL,
    TEST_USER_EMAIL,
    TEST_USER_ID,
)
from tests._utils.date_time import get_current_timestamp_str
from tests._utils.notices import get_user_notices

_ACCESS_REQUEST = {
    "type": "project-access",
    "resource_id": TEST_PROJECT_ID,
    "reason": "let me in",
}
_QPU_SECONDS_REQUEST = {
    "type": "project-qpu-seconds",
    "resource_id": TEST_PROJECT_ID,
    "reason": "more please",
    "metadata": {"seconds": 120},
}
_PULSE_ACCESS_REQUEST = {
    "type": "project-pulse-access",
    "resource_id": TEST_PROJECT_ID,
    "reason": "to calibrate my own gates",
}
_CREATE_PROJECT_REQUEST = {
    "type": "create-project",
    "resource_id": TEST_OUTSIDER_ID,
    "reason": "for my thesis",
    "metadata": {
        "name": "thesis project",
        "admin_email": TEST_OUTSIDER_EMAIL,
        "user_emails": [TEST_USER_EMAIL],
        "qpu_seconds": 3600,
    },
}
_PENDING_ACCESS_REQUEST_ID = "6707c09fd3b66d50e2630b79"
_REJECTED_QPU_REQUEST_ID = "6707c0bcd3b66d50e2630b7a"
_APPROVED_QPU_REQUEST_ID = "6707c0cad3b66d50e2630b7b"
_PENDING_CREATE_REQUEST_ID = "6707c0dbd3b66d50e2630b7c"
_PENDING_NO_QPU_ACCESS_REQUEST_ID = "6707c0ead3b66d50e2630b7d"


def test_request_project_access(client, outsider_jwt_cookie, db):
    """POST /me/requests/ creates a pending request directed to the project admin"""
    with client as client:
        response = client.post(
            "/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST
        )
        got = response.json()

        assert response.status_code == 201
        assert got["type"] == "project-access"
        assert got["status"] == "pending"
        assert got["target"] == "project"
        assert got["resource_id"] == TEST_PROJECT_ID
        assert got["requester_id"] == TEST_OUTSIDER_ID
        assert got["requester_name"] == "outsider.doe"
        assert got["target_user_ids"] == [TEST_USER_ID]
        assert got["metadata"] == {"resource": "project"}
        assert db.get(Request, got["id"]) is not None


def test_request_project_access_notifies_the_project_admin(
    client, outsider_jwt_cookie, db
):
    """Filing an access request reaches the admin of the project, not the requester"""
    with client as client:
        request_id = client.post(
            "/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST
        ).json()["id"]
        admin_notices = get_user_notices(db, TEST_USER_ID)

        assert [item.type for item in admin_notices] == [
            NoticeTypeId.PROJECT_ACCESS_REQUESTED
        ]
        assert admin_notices[0].title == f"Access request for {TEST_PROJECT_NAME}"
        assert admin_notices[0].body == (
            f"outsider.doe is asking to join {TEST_PROJECT_NAME}: let me in"
        )
        assert admin_notices[0].ref_type == "project"
        assert admin_notices[0].ref_id == request_id
        assert get_user_notices(db, TEST_OUTSIDER_ID) == []


def test_request_access_to_unknown_project(client, outsider_jwt_cookie, db):
    """POST /me/requests/ answers 404 for a project that does not exist"""
    project_id = generate_id()

    with client as client:
        response = client.post(
            "/me/requests/",
            cookies=outsider_jwt_cookie,
            json={**_ACCESS_REQUEST, "resource_id": project_id},
        )

        assert response.status_code == 404
        assert response.json() == {"detail": f"project {project_id} not found"}
        assert db.count(Request) == 0


def test_request_access_to_personal_project(
    client, outsider_jwt_cookie, personal_project
):
    """Personal projects answer 404 identically, so they cannot be probed for"""
    project_id = personal_project["_id"]

    with client as client:
        response = client.post(
            "/me/requests/",
            cookies=outsider_jwt_cookie,
            json={**_ACCESS_REQUEST, "resource_id": str(project_id)},
        )

        assert response.status_code == 404
        assert response.json() == {"detail": f"project {project_id} not found"}


def test_request_qpu_seconds(client, user_jwt_cookie, db):
    """A project member's request for QPU time goes to the superusers"""
    with client as client:
        response = client.post(
            "/me/requests/", cookies=user_jwt_cookie, json=_QPU_SECONDS_REQUEST
        )
        got = response.json()
        superuser_notices = get_user_notices(db, TEST_SUPERUSER_ID)

        assert response.status_code == 201
        assert got["target"] == "system"
        assert got["target_user_ids"] == [TEST_SUPERUSER_ID]
        assert got["metadata"]["seconds"] == 120
        assert [item.type for item in superuser_notices] == [
            NoticeTypeId.QPU_SECONDS_REQUESTED
        ]
        assert "120.0s" in superuser_notices[0].body


def test_non_member_request_qpu_seconds(client, outsider_jwt_cookie, db):
    """Only members of a project can ask for its QPU time"""
    with client as client:
        response = client.post(
            "/me/requests/", cookies=outsider_jwt_cookie, json=_QPU_SECONDS_REQUEST
        )

        assert response.status_code == 403
        assert response.json() == {
            "detail": f"operation not permitted on resource {TEST_PROJECT_ID}"
        }
        assert db.count(Request) == 0


@pytest.mark.parametrize("metadata", [None, {}, {"seconds": 0}])
def test_request_qpu_seconds_without_seconds(client, user_jwt_cookie, db, metadata):
    """A request for QPU time must say how many seconds it wants"""
    with client as client:
        response = client.post(
            "/me/requests/",
            cookies=user_jwt_cookie,
            json={**_QPU_SECONDS_REQUEST, "metadata": metadata},
        )

        assert response.status_code == 422
        assert db.count(Request) == 0


def test_request_project_creation(client, outsider_jwt_cookie, db):
    """Anyone can ask the superusers for a new project"""
    with client as client:
        response = client.post(
            "/me/requests/", cookies=outsider_jwt_cookie, json=_CREATE_PROJECT_REQUEST
        )
        got = response.json()

        assert response.status_code == 201
        assert got["target_user_ids"] == [TEST_SUPERUSER_ID]
        assert got["metadata"]["name"] == "thesis project"
        assert got["metadata"]["admin_email"] == TEST_OUTSIDER_EMAIL
        assert got["metadata"]["user_emails"] == [TEST_USER_EMAIL]
        assert get_user_notices(db, TEST_SUPERUSER_ID)[0].title == (
            "Create request for thesis project"
        )


@pytest.mark.parametrize("request_type", ["close-project", "transfer-project"])
def test_request_project_change_by_its_admin(client, user_jwt_cookie, db, request_type):
    """The admin of a project can ask the superusers to close or transfer it"""
    with client as client:
        response = client.post(
            "/me/requests/",
            cookies=user_jwt_cookie,
            json={
                "type": request_type,
                "resource_id": TEST_PROJECT_ID,
                "reason": "we are done",
                "metadata": {"admin_email": TEST_SYSTEM_USER_EMAIL},
            },
        )

        assert response.status_code == 201
        assert response.json()["target_user_ids"] == [TEST_SUPERUSER_ID]


@pytest.mark.parametrize("request_type", ["close-project", "transfer-project"])
def test_request_project_change_by_non_admin(
    client, system_user_jwt_cookie, db, request_type
):
    """A member who does not administer a project cannot ask to close or transfer it"""
    with client as client:
        response = client.post(
            "/me/requests/",
            cookies=system_user_jwt_cookie,
            json={
                "type": request_type,
                "resource_id": TEST_PROJECT_ID,
                "reason": "we are done",
                "metadata": {"admin_email": TEST_SYSTEM_USER_EMAIL},
            },
        )

        assert response.status_code == 403
        assert db.count(Request) == 0


def test_unauthenticated_create_request(client, db):
    """POST /me/requests/ requires a signed-in user"""
    with client as client:
        response = client.post("/me/requests/", json=_ACCESS_REQUEST)

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
        assert db.count(Request) == 0


def test_view_requests_as_approver(client, user_jwt_cookie, inserted_requests):
    """GET /me/requests/ returns the requests awaiting the user, newest first"""
    with client as client:
        response = client.get("/me/requests/", cookies=user_jwt_cookie)
        got = response.json()

        assert response.status_code == 200
        assert got["skip"] == 0
        assert got["limit"] is None
        assert [item["id"] for item in got["data"]] == [
            _PENDING_NO_QPU_ACCESS_REQUEST_ID,
            _PENDING_ACCESS_REQUEST_ID,
        ]


def test_view_requests_as_requester(client, user_jwt_cookie, inserted_requests):
    """GET /me/requests/?role=requester returns the requests the user made"""
    with client as client:
        response = client.get("/me/requests/?role=requester", cookies=user_jwt_cookie)

        assert [item["id"] for item in response.json()["data"]] == [
            _REJECTED_QPU_REQUEST_ID
        ]


def test_view_requests_by_status_and_type(client, admin_jwt_cookie, inserted_requests):
    """GET /me/requests/?status=...&type=... returns only the matching requests"""
    with client as client:
        pending = client.get("/me/requests/?status=pending", cookies=admin_jwt_cookie)
        decided_qpu = client.get(
            "/me/requests/?status=approved&status=rejected&type=project-qpu-seconds",
            cookies=admin_jwt_cookie,
        )

        assert [item["id"] for item in pending.json()["data"]] == [
            _PENDING_CREATE_REQUEST_ID
        ]
        assert [item["id"] for item in decided_qpu.json()["data"]] == [
            _APPROVED_QPU_REQUEST_ID,
            _REJECTED_QPU_REQUEST_ID,
        ]


def test_paginate_requests(client, admin_jwt_cookie, inserted_requests):
    """GET /me/requests/?skip=...&limit=...&sort=... returns the requested page"""
    with client as client:
        response = client.get(
            "/me/requests/?skip=1&limit=1&sort=created_at", cookies=admin_jwt_cookie
        )
        got = response.json()

        assert got["skip"] == 1
        assert got["limit"] == 1
        assert [item["id"] for item in got["data"]] == [_APPROVED_QPU_REQUEST_ID]


def test_unauthenticated_view_requests(client, inserted_requests):
    """GET /me/requests/ requires a signed-in user"""
    with client as client:
        response = client.get("/me/requests/")

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


def test_approve_project_access(client, outsider_jwt_cookie, user_jwt_cookie, db):
    """Approving an access request adds the requester to the project and tells them"""
    with client as client:
        request_id = client.post(
            "/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST
        ).json()["id"]
        response = client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )
        got = response.json()
        project = db.get(Project, TEST_PROJECT_ID)
        requester_notices = get_user_notices(db, TEST_OUTSIDER_ID)

        assert response.status_code == 200
        assert got["status"] == "approved"
        assert got["approver_id"] == TEST_USER_ID
        assert got["approver_name"] == "john.doe"
        assert project.user_ids.count(TEST_OUTSIDER_ID) == 1
        assert [item.type for item in requester_notices] == [
            NoticeTypeId.PROJECT_ACCESS_APPROVED
        ]
        assert requester_notices[0].body == (
            f"john.doe approved your request to join {TEST_PROJECT_NAME}."
        )


def test_deciding_a_request_clears_its_prompt(
    client, outsider_jwt_cookie, user_jwt_cookie, db
):
    """Deciding a request expires the approver's 'please decide this' notice"""
    with client as client:
        request_id = client.post(
            "/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST
        ).json()["id"]
        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )
        outcome = get_user_notices(db, TEST_OUTSIDER_ID)[0]

        assert get_user_notices(db, TEST_USER_ID) == []
        assert outcome.read_at is None


def test_deciding_a_request_stamps_when(
    client, user_jwt_cookie, db, inserted_requests, freezer
):
    """Deciding a request sets its updated_at to the time of the decision"""
    now = get_current_timestamp_str()

    with client as client:
        response = client.put(
            f"/me/requests/{_PENDING_ACCESS_REQUEST_ID}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )
        request = db.get(Request, _PENDING_ACCESS_REQUEST_ID)

        assert response.json()["updated_at"] == now
        assert request.updated_at == now


def test_reject_project_access(client, outsider_jwt_cookie, user_jwt_cookie, db):
    """Rejecting records the reason, leaves membership untouched and tells the requester why"""
    with client as client:
        request_id = client.post(
            "/me/requests/", cookies=outsider_jwt_cookie, json=_ACCESS_REQUEST
        ).json()["id"]
        response = client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "rejected", "rejection_reason": "wrong team"},
        )
        got = response.json()
        project = db.get(Project, TEST_PROJECT_ID)
        requester_notices = get_user_notices(db, TEST_OUTSIDER_ID)

        assert response.status_code == 200
        assert got["status"] == "rejected"
        assert got["rejection_reason"] == "wrong team"
        assert TEST_OUTSIDER_ID not in project.user_ids
        assert requester_notices[0].type == NoticeTypeId.PROJECT_ACCESS_REJECTED
        assert requester_notices[0].body.endswith("wrong team")


def test_approve_qpu_seconds(client, user_jwt_cookie, admin_jwt_cookie, db):
    """Approving a QPU request adds the seconds to the project and tells the requester"""
    project_before = db.get(Project, TEST_PROJECT_ID)

    with client as client:
        request_id = client.post(
            "/me/requests/", cookies=user_jwt_cookie, json=_QPU_SECONDS_REQUEST
        ).json()["id"]
        response = client.put(
            f"/me/requests/{request_id}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )
        project_after = db.get(Project, TEST_PROJECT_ID)
        requester_notices = get_user_notices(db, TEST_USER_ID)

        assert response.status_code == 200
        assert project_after.qpu_seconds == project_before.qpu_seconds + 120
        assert [item.type for item in requester_notices] == [
            NoticeTypeId.QPU_SECONDS_GRANTED
        ]
        assert requester_notices[0].title == (
            f"120.0s of QPU time added to {TEST_PROJECT_NAME}"
        )


def test_request_pulse_access(client, user_jwt_cookie, db):
    """A project member's request for pulse-level jobs goes to the superusers"""
    with client as client:
        response = client.post(
            "/me/requests/", cookies=user_jwt_cookie, json=_PULSE_ACCESS_REQUEST
        )
        superuser_notices = get_user_notices(db, TEST_SUPERUSER_ID)

        assert response.status_code == 201
        assert response.json()["target_user_ids"] == [TEST_SUPERUSER_ID]
        assert [item.type for item in superuser_notices] == [
            NoticeTypeId.PULSE_ACCESS_REQUESTED
        ]
        assert "to calibrate my own gates" in superuser_notices[0].body


def test_non_member_request_pulse_access(client, outsider_jwt_cookie, db):
    """Only members of a project can ask that its jobs be pulse-level"""
    with client as client:
        response = client.post(
            "/me/requests/", cookies=outsider_jwt_cookie, json=_PULSE_ACCESS_REQUEST
        )

        assert response.status_code == 403
        assert db.count(Request) == 0


@pytest.mark.parametrize(
    "decision, is_pulse_allowed, notice_type",
    [
        ({"status": "approved"}, True, NoticeTypeId.PULSE_ACCESS_GRANTED),
        (
            {"status": "rejected", "rejection_reason": "not yet"},
            False,
            NoticeTypeId.PULSE_ACCESS_DENIED,
        ),
    ],
    ids=["approved", "rejected"],
)
def test_decide_pulse_access(
    client,
    user_jwt_cookie,
    admin_jwt_cookie,
    db,
    decision,
    is_pulse_allowed,
    notice_type,
):
    """Approving a request for pulse-level jobs allows them on its project, and either
    decision tells the requester"""
    with client as client:
        request_id = client.post(
            "/me/requests/", cookies=user_jwt_cookie, json=_PULSE_ACCESS_REQUEST
        ).json()["id"]
        response = client.put(
            f"/me/requests/{request_id}", cookies=admin_jwt_cookie, json=decision
        )
        project = db.get(Project, TEST_PROJECT_ID)
        requester_notices = get_user_notices(db, TEST_USER_ID)

        assert response.status_code == 200
        assert project.is_pulse_allowed is is_pulse_allowed
        assert [item.type for item in requester_notices] == [notice_type]
        assert TEST_PROJECT_NAME in requester_notices[0].title


def test_approve_project_creation(client, admin_jwt_cookie, db, inserted_requests):
    """Approving a create-project request creates the project that was described"""
    with client as client:
        response = client.put(
            f"/me/requests/{_PENDING_CREATE_REQUEST_ID}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )
        project = db.find_one(Project, {"name": "thesis project"})

        assert response.status_code == 200
        assert project.admin_id == TEST_OUTSIDER_ID
        assert project.user_ids == [
            TEST_USER_ID,
            TEST_OUTSIDER_ID,
        ]
        assert project.qpu_seconds == 3600


def test_approve_project_creation_for_unknown_users(
    client, outsider_jwt_cookie, admin_jwt_cookie, db
):
    """Approval creates the users named in the request who do not exist yet"""
    payload = {
        **_CREATE_PROJECT_REQUEST,
        "metadata": {
            **_CREATE_PROJECT_REQUEST["metadata"],
            "user_emails": ["no@such.user"],
        },
    }

    with client as client:
        request_id = client.post(
            "/me/requests/", cookies=outsider_jwt_cookie, json=payload
        ).json()["id"]
        response = client.put(
            f"/me/requests/{request_id}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )
        user = db.find_one(User, {"email": "no@such.user"})
        project = db.find_one(Project, {"name": "thesis project"})

        assert response.status_code == 200
        assert project.user_ids == [
            user.id,
            TEST_OUTSIDER_ID,
        ]


def test_approve_project_creation_with_existing_name(
    client, outsider_jwt_cookie, admin_jwt_cookie, db
):
    """Approval fails and leaves the request pending when the project name is taken"""
    payload = {
        **_CREATE_PROJECT_REQUEST,
        "metadata": {**_CREATE_PROJECT_REQUEST["metadata"], "name": TEST_PROJECT_NAME},
    }

    with client as client:
        request_id = client.post(
            "/me/requests/", cookies=outsider_jwt_cookie, json=payload
        ).json()["id"]
        response = client.put(
            f"/me/requests/{request_id}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": f"a project named '{TEST_PROJECT_NAME}' already exists"
        }
        assert db.get(Request, request_id).status == "pending"


def test_approve_project_creation_notifies_the_members(
    client, admin_jwt_cookie, db, inserted_requests
):
    """The members of a project created by approval hear that they were added"""
    with client as client:
        client.put(
            f"/me/requests/{_PENDING_CREATE_REQUEST_ID}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )
        member_notices = get_user_notices(db, TEST_USER_ID)

        assert [item.type for item in member_notices] == [
            NoticeTypeId.PROJECT_MEMBERSHIP_GRANTED
        ]
        assert member_notices[0].title == "You were added to thesis project"


def test_approve_project_close(client, user_jwt_cookie, admin_jwt_cookie, db):
    """Approving a close-project request deletes the project, keeping a copy"""
    with client as client:
        request_id = client.post(
            "/me/requests/",
            cookies=user_jwt_cookie,
            json={
                "type": "close-project",
                "resource_id": TEST_PROJECT_ID,
                "reason": "we are done",
            },
        ).json()["id"]
        response = client.put(
            f"/me/requests/{request_id}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )

        assert response.status_code == 200
        assert db.get(Project, TEST_PROJECT_ID) is None
        assert db.get(DeletedProject, TEST_PROJECT_ID) is not None


def test_approve_project_close_names_the_closed_project(
    client, user_jwt_cookie, admin_jwt_cookie, db
):
    """The requester is told which project was closed, though it no longer exists"""
    with client as client:
        request_id = client.post(
            "/me/requests/",
            cookies=user_jwt_cookie,
            json={
                "type": "close-project",
                "resource_id": TEST_PROJECT_ID,
                "reason": "we are done",
            },
        ).json()["id"]
        client.put(
            f"/me/requests/{request_id}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )
        requester_notices = get_user_notices(db, TEST_USER_ID)

        assert requester_notices[-1].type == NoticeTypeId.PROJECT_CLOSE_APPROVED
        assert requester_notices[-1].title == (
            f"Your project {TEST_PROJECT_NAME} was closed"
        )


def test_approve_project_transfer(client, user_jwt_cookie, admin_jwt_cookie, db):
    """Approving a transfer-project request hands the project to the named user"""
    with client as client:
        request_id = client.post(
            "/me/requests/",
            cookies=user_jwt_cookie,
            json={
                "type": "transfer-project",
                "resource_id": TEST_PROJECT_ID,
                "reason": "I am leaving",
                "metadata": {"admin_email": TEST_OUTSIDER_EMAIL},
            },
        ).json()["id"]
        response = client.put(
            f"/me/requests/{request_id}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )
        project = db.get(Project, TEST_PROJECT_ID)

        assert response.status_code == 200
        assert project.admin_id == TEST_OUTSIDER_ID
        assert TEST_OUTSIDER_ID in project.user_ids


def test_decide_request_twice(client, user_jwt_cookie, inserted_requests):
    """A decided request cannot be decided again"""
    with client as client:
        client.put(
            f"/me/requests/{_PENDING_ACCESS_REQUEST_ID}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )
        response = client.put(
            f"/me/requests/{_PENDING_ACCESS_REQUEST_ID}",
            cookies=user_jwt_cookie,
            json={"status": "rejected"},
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "no match found"}


def test_non_approver_cannot_decide_request(
    client, outsider_jwt_cookie, db, inserted_requests
):
    """Only the users a request is directed to can decide it, not even its requester"""
    with client as client:
        response = client.put(
            f"/me/requests/{_PENDING_ACCESS_REQUEST_ID}",
            cookies=outsider_jwt_cookie,
            json={"status": "approved"},
        )
        request = db.get(Request, _PENDING_ACCESS_REQUEST_ID)
        project = db.get(Project, TEST_PROJECT_ID)

        assert response.status_code == 404
        assert request.status == "pending"
        assert TEST_OUTSIDER_ID not in project.user_ids


def test_update_unknown_request(client, user_jwt_cookie):
    """PUT /me/requests/{id} answers 404 for a request that does not exist"""
    with client as client:
        response = client.put(
            f"/me/requests/{generate_id()}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        assert response.status_code == 404


def test_update_request_fields_other_than_the_decision(
    client, user_jwt_cookie, inserted_requests
):
    """Only the status and the rejection reason of a request can be updated"""
    with client as client:
        response = client.put(
            f"/me/requests/{_PENDING_ACCESS_REQUEST_ID}",
            cookies=user_jwt_cookie,
            json={"reason": "a better reason"},
        )

        assert response.status_code == 422


def test_unauthenticated_update_request(client, db, inserted_requests):
    """PUT /me/requests/{id} requires a signed-in user"""
    with client as client:
        response = client.put(
            f"/me/requests/{_PENDING_ACCESS_REQUEST_ID}", json={"status": "approved"}
        )

        assert response.status_code == 401
        assert db.get(Request, _PENDING_ACCESS_REQUEST_ID).status == ("pending")
