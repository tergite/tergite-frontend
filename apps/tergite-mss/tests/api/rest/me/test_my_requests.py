# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import copy
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from pytest_lazyfixture import lazy_fixture

from services.auth import Project
from services.requests import Request
from tests._utils.auth import (
    TEST_SUPERUSER_DICT,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_DICT,
    TEST_SYSTEM_USER_ID,
    TEST_USER_DICT,
    TEST_USER_ID,
    get_db_record,
)
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import insert_in_collection
from tests.conftest import PROJECT_LIST, get_auth_cookie

_REQ_STATUSES = ["pending", "rejected", "approved"]
_USER_REQUEST_COLLECTION = "auth_user_requests"
_USER_REQUESTS_IN_DB = load_json_fixture("user_requests.json")

_QPU_TIME_USER_REQUESTS_IN_DB = [
    item for item in _USER_REQUESTS_IN_DB if item["type"] == "project-qpu-seconds"
]
_PENDING_QPU_TIME_REQUESTS_IN_DB = [
    item for item in _QPU_TIME_USER_REQUESTS_IN_DB if item["status"] == "pending"
]

_USER_ID_COOKIES_FIXTURE = [
    (TEST_USER_ID, lazy_fixture("user_jwt_cookie")),
    (TEST_SUPERUSER_ID, lazy_fixture("admin_jwt_cookie")),
]

_USER_ID_COOKIES_REQ_STATUS_FIXTURE = [
    (pair[0], pair[1], status)
    for status in _REQ_STATUSES
    for pair in _USER_ID_COOKIES_FIXTURE
]

_USER_ID_COOKIES_REQ_PROJECT_ID_FIXTURE = [
    (pair[0], pair[1], project["_id"])
    for project in PROJECT_LIST
    for pair in _USER_ID_COOKIES_FIXTURE
]
_USER_ID_COOKIES_REQ_PROJECT_ID_AND_STATUS_FIXTURE = [
    (pair[0], pair[1], project["_id"], status)
    for project in PROJECT_LIST
    for status in _REQ_STATUSES
    for pair in _USER_ID_COOKIES_FIXTURE
]
_QPU_TIME_REQUEST = {
    "seconds": 150000.0,
    "reason": "Some other reason again",
}

_USER_MAP = {
    str(user["_id"]): user
    for user in [TEST_USER_DICT, TEST_SYSTEM_USER_DICT, TEST_SUPERUSER_DICT]
}
_USER_ID_COOKIE_QPU_TIME_REQUESTS = [
    (
        user_id,
        get_auth_cookie(user_id),
        {**_QPU_TIME_REQUEST, "project_id": project["_id"]},
        project["name"],
        _USER_MAP[user_id]["email"].split("@")[0],
    )
    for project in PROJECT_LIST
    for user_id in project["user_ids"]
]

_NON_MEMBER_ID_COOKIE_QPU_TIME_REQUESTS = [
    (
        user_id,
        get_auth_cookie(user_id),
        {**_QPU_TIME_REQUEST, "project_id": project["_id"]},
    )
    for project in PROJECT_LIST
    for user_id in [TEST_USER_ID, TEST_SUPERUSER_ID, TEST_SYSTEM_USER_ID]
    if user_id not in project["user_ids"]
]


@pytest.mark.parametrize("user_id, cookies", _USER_ID_COOKIES_FIXTURE)
def test_view_all_qpu_time_user_requests(
    user_id, cookies, client, inserted_project_ids, db
):
    """Any user can view all user requests at /admin/qpu-time-requests"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=_QPU_TIME_USER_REQUESTS_IN_DB,
    )

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/admin/qpu-time-requests/", cookies=cookies)

        got = response.json()
        user_request_list = [
            _db_to_http_item(item) for item in _QPU_TIME_USER_REQUESTS_IN_DB
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": user_request_list}


@pytest.mark.parametrize("user_id", [TEST_USER_ID, TEST_SUPERUSER_ID])
def test_non_authenticated_qpu_time_user_requests_view(
    user_id, client, inserted_project_ids, db
):
    """Only authenticated users can view user requests at /admin/qpu-time-requests"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=_QPU_TIME_USER_REQUESTS_IN_DB,
    )

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/admin/qpu-time-requests/")
        got = response.json()
        assert response.status_code == 401
        assert got == {"detail": "Unauthorized"}


@pytest.mark.parametrize(
    "user_id, cookies, status", _USER_ID_COOKIES_REQ_STATUS_FIXTURE
)
def test_view_qpu_time_user_requests_filtered_by_status(
    user_id, cookies, status, client, inserted_project_ids, db
):
    """Any user can view user requests at /admin/qpu-time-requests?status=... filtered by status"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=_QPU_TIME_USER_REQUESTS_IN_DB,
    )

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(
            f"/admin/qpu-time-requests/?status={status}", cookies=cookies
        )

        got = response.json()
        user_request_list = [
            _db_to_http_item(item)
            for item in _QPU_TIME_USER_REQUESTS_IN_DB
            if item["status"] == status
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": user_request_list}


@pytest.mark.parametrize(
    "user_id, cookies, project_id", _USER_ID_COOKIES_REQ_PROJECT_ID_FIXTURE
)
def test_view_qpu_time_user_requests_filtered_by_project_id(
    user_id, cookies, project_id, client, inserted_project_ids, db
):
    """Any user can view user requests at /admin/qpu-time-requests/?project_id=... filtered by project_id"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=_QPU_TIME_USER_REQUESTS_IN_DB,
    )

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(
            f"/admin/qpu-time-requests/?project_id={project_id}", cookies=cookies
        )

        got = response.json()
        user_request_list = [
            _db_to_http_item(item)
            for item in _QPU_TIME_USER_REQUESTS_IN_DB
            if item["request"]["project_id"] == project_id
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": user_request_list}


@pytest.mark.parametrize(
    "user_id, cookies, project_id, status",
    _USER_ID_COOKIES_REQ_PROJECT_ID_AND_STATUS_FIXTURE,
)
def test_view_qpu_time_user_requests_filtered_by_project_id_and_status(
    user_id, cookies, project_id, status, client, inserted_project_ids, db
):
    """User can filter user requests /admin/qpu-time-requests/?project_id=...&status=... by project_id and status"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=_QPU_TIME_USER_REQUESTS_IN_DB,
    )

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(
            f"/admin/qpu-time-requests/?project_id={project_id}&status={status}",
            cookies=cookies,
        )

        got = response.json()
        user_request_list = [
            _db_to_http_item(item)
            for item in _QPU_TIME_USER_REQUESTS_IN_DB
            if item["request"]["project_id"] == project_id and item["status"] == status
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": user_request_list}


@pytest.mark.parametrize(
    "user_id, cookies, request_body, project_name, requester_name",
    _USER_ID_COOKIE_QPU_TIME_REQUESTS,
)
def test_create_qpu_time_user_request(
    user_id,
    cookies,
    request_body,
    project_name,
    requester_name,
    client,
    inserted_project_ids,
    db,
    freezer,
):
    """Any project member can create a user request at /admin/qpu-time-requests/"""
    timestamp = (
        datetime.now(timezone.utc)
        .isoformat("T", timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    # using context manager to ensure on_startup runs
    with client as client:
        filter_obj = {"request.project_id": request_body["project_id"]}
        assert get_db_record(db, Request, _filter=filter_obj) is None

        response = client.post(
            "/admin/qpu-time-requests/", cookies=cookies, json=request_body
        )

        got = response.json()
        expected = {
            "request": {**request_body, "project_name": project_name},
            "requester_id": user_id,
            "requester_name": requester_name,
            "updated_at": timestamp,
            "created_at": timestamp,
            "type": "project-qpu-seconds",
            "status": "pending",
            "rejection_reason": None,
            "approver_id": None,
            "approver_name": None,
            "approver_scope": "system-admin",
            "project_id": request_body["project_id"],
        }
        assert isinstance(got.pop("id"), str)
        assert response.status_code == 201
        assert got == expected
        assert get_db_record(db, Request, _filter=filter_obj) is not None


@pytest.mark.parametrize(
    "user_id, cookies, request_body", _NON_MEMBER_ID_COOKIE_QPU_TIME_REQUESTS
)
def test_non_member_create_qpu_time_user_request(
    user_id, cookies, request_body, client, inserted_project_ids, db
):
    """Non project members can not create a user request at /admin/qpu-time-requests/"""
    # using context manager to ensure on_startup runs
    with client as client:
        filter_obj = {"request.project_id": request_body["project_id"]}
        response = client.post(
            "/admin/qpu-time-requests/", cookies=cookies, json=request_body
        )

        got = response.json()
        assert response.status_code == 403
        assert got == {"detail": "Forbidden"}
        assert get_db_record(db, Request, _filter=filter_obj) is None


@pytest.mark.parametrize("project", PROJECT_LIST)
def test_unauthenticated_create_qpu_time_user_request(
    project, client, inserted_project_ids, db
):
    """Unauthenticated users can not create a user request at /admin/qpu-time-requests/"""
    # using context manager to ensure on_startup runs
    with client as client:
        request_body = {**_QPU_TIME_REQUEST, "project_id": project["_id"]}
        filter_obj = {"request.project_id": request_body["project_id"]}
        assert get_db_record(db, Request, _filter=filter_obj) is None

        response = client.post("/admin/qpu-time-requests/", json=request_body)

        got = response.json()
        assert response.status_code == 401
        assert got == {"detail": "Unauthorized"}
        assert get_db_record(db, Request, _filter=filter_obj) is None


def test_view_user_requests(admin_jwt_cookie, client, inserted_project_ids, db):
    """GET /admin/user-requests/ should return the matched user requests"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=_USER_REQUESTS_IN_DB,
    )

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/admin/user-requests/", cookies=admin_jwt_cookie)

        got = response.json()
        user_request_list = [_db_to_http_item(item) for item in _USER_REQUESTS_IN_DB]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": user_request_list}


@pytest.mark.parametrize("status", _REQ_STATUSES)
def test_view_user_requests_filtered_by_status(
    status, admin_jwt_cookie, client, inserted_project_ids, db
):
    """GET /admin/user-requests/?status=... should return the matched user requests"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=_USER_REQUESTS_IN_DB,
    )

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(
            f"/admin/user-requests/?status={status}", cookies=admin_jwt_cookie
        )

        got = response.json()
        user_request_list = [
            _db_to_http_item(item)
            for item in _USER_REQUESTS_IN_DB
            if item["status"] == status
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": user_request_list}


def test_non_admin_view_user_requests(
    user_jwt_cookie, client, inserted_project_ids, db
):
    """GET /admin/user-requests/?status=... should return the matched user requests"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=_USER_REQUESTS_IN_DB,
    )

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/admin/user-requests/", cookies=user_jwt_cookie)

        got = response.json()
        assert response.status_code == 403
        assert got == {"detail": "Forbidden"}


@pytest.mark.parametrize("user_request", _PENDING_QPU_TIME_REQUESTS_IN_DB)
def test_approve_qpu_seconds_user_requests(
    user_request, admin_jwt_cookie, client, inserted_projects, db
):
    """Approving QPU time request via PUT /admin/user-requests/{_id} increments QPU time on project"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=[user_request],
    )
    payload = {"status": "approved"}
    approver_details = {
        "approver_id": str(TEST_SUPERUSER_DICT["_id"]),
        "approver_name": TEST_SUPERUSER_DICT["email"].split("@")[0],
    }
    project_id = user_request["request"]["project_id"]
    additional_seconds = user_request["request"]["seconds"]

    # using context manager to ensure on_startup runs
    with client as client:
        original_project = get_db_record(db, Project, project_id)
        response = client.put(
            f"/admin/user-requests/{user_request['_id']}",
            cookies=admin_jwt_cookie,
            json=payload,
        )

        got = response.json()
        expected = {**_db_to_http_item(user_request), **payload, **approver_details}
        updated_project = get_db_record(db, Project, project_id)

        assert response.status_code == 200
        assert got == expected
        assert updated_project == {
            **original_project,
            "qpu_seconds": original_project["qpu_seconds"] + additional_seconds,
            "low_qpu_notified_at": None,
        }


@pytest.mark.parametrize("user_request", _PENDING_QPU_TIME_REQUESTS_IN_DB)
def test_reject_qpu_seconds_user_requests(
    user_request, admin_jwt_cookie, client, inserted_project_ids, db
):
    """Rejecting QPU time request via PUT /admin/user-requests/{_id} leaves project intact"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=[user_request],
    )
    payload = {"status": "rejected"}
    approver_details = {
        "approver_id": str(TEST_SUPERUSER_DICT["_id"]),
        "approver_name": TEST_SUPERUSER_DICT["email"].split("@")[0],
    }
    project_id = user_request["request"]["project_id"]

    # using context manager to ensure on_startup runs
    with client as client:
        original_project = get_db_record(db, Project, project_id)
        response = client.put(
            f"/admin/user-requests/{user_request['_id']}",
            cookies=admin_jwt_cookie,
            json=payload,
        )

        got = response.json()
        expected = {**_db_to_http_item(user_request), **payload, **approver_details}
        updated_project = get_db_record(db, Project, project_id)

        assert response.status_code == 200
        assert got == expected
        assert updated_project == original_project


@pytest.mark.parametrize("user_request", _PENDING_QPU_TIME_REQUESTS_IN_DB)
def test_non_admin_update_user_requests(
    user_request, user_jwt_cookie, client, inserted_project_ids, db
):
    """Non admin users are not allowed to PUT /admin/user-requests/{_id}"""
    insert_in_collection(
        database=db,
        collection_name=_USER_REQUEST_COLLECTION,
        data=[user_request],
    )
    payload = {"status": "approved"}
    user_request_id = user_request["_id"]

    # using context manager to ensure on_startup runs
    with client as client:
        original_user_request = get_db_record(db, Request, user_request_id)
        response = client.put(
            f"/admin/user-requests/{user_request_id}",
            cookies=user_jwt_cookie,
            json=payload,
        )

        got = response.json()
        updated_user_request = get_db_record(db, Request, user_request_id)

        assert response.status_code == 403
        assert got == {"detail": "Forbidden"}
        assert updated_user_request == original_user_request


@pytest.mark.parametrize("user_request", _PENDING_QPU_TIME_REQUESTS_IN_DB)
def test_update_non_existent_user_requests(
    user_request, admin_jwt_cookie, client, inserted_project_ids, db
):
    """PUT /admin/user-requests/{_id} where _id does not exist throws a 404 error"""
    payload = {"status": "approved"}
    user_request_id = user_request["_id"]

    # using context manager to ensure on_startup runs
    with client as client:
        original_user_request = get_db_record(db, Request, user_request_id)
        response = client.put(
            f"/admin/user-requests/{user_request_id}",
            cookies=admin_jwt_cookie,
            json=payload,
        )

        got = response.json()
        updated_user_request = get_db_record(db, Request, user_request_id)

        assert response.status_code == 404
        assert got == {"detail": f"{user_request_id} not found"}
        assert updated_user_request == original_user_request


def _db_to_http_item(db_item: Dict[str, Any]) -> Dict[str, Any]:
    """Converts a database item into an item that can be expected to be returned by HTTP server

    Args:
        db_item: the item in the database

    Returns:
        the item as would be seen from an HTTP response
    """
    item = copy.deepcopy(db_item)
    item["id"] = str(item.pop("_id"))
    # fields the server fills in from model defaults
    item.setdefault("approver_scope", "system-admin")
    item.setdefault("project_id", None)
    return item
