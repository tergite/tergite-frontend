# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Integration tests for the routes for the admin"""
import copy
from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, TypedDict

import pytest
from pytest_lazyfixture import lazy_fixture
from typing_extensions import TypeVar

from services.auth import Project
from services.auth.projects.dtos import DeletedProject
from services.auth.user_requests import UserRequest

from ..._utils.auth import (
    TEST_NO_QPU_PROJECT_DICT,
    TEST_PROJECT_DICT,
    TEST_PROJECT_ID,
    TEST_SUPERUSER_DICT,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_DICT,
    TEST_SYSTEM_USER_ID,
    TEST_USER_DICT,
    TEST_USER_ID,
    USER_ID_EMAIL_MAP,
    get_db_record,
)
from ..._utils.date_time import get_timestamp_str
from ..._utils.fixtures import load_json_fixture
from ..._utils.mongodb import find_in_collection, insert_in_collection
from ..._utils.records import prune
from ...conftest import PROJECT_LIST, get_auth_cookie

_REQ_STATUSES = ["pending", "rejected", "approved"]
_USER_REQUEST_COLLECTION = "auth_user_requests"
_USER_REQUESTS_IN_DB = load_json_fixture("user_requests.json")
_PROJECT_CREATE_LIST = load_json_fixture("project_create_list.json")
_PROJECT_UPDATE_LIST = load_json_fixture("project_update_list.json")
_QPU_TIME_USER_REQUESTS_IN_DB = [
    item for item in _USER_REQUESTS_IN_DB if item["type"] == "project-qpu-seconds"
]
_PENDING_QPU_TIME_REQUESTS_IN_DB = [
    item for item in _QPU_TIME_USER_REQUESTS_IN_DB if item["status"] == "pending"
]
_USER_MAP = {
    str(user["_id"]): user
    for user in [TEST_USER_DICT, TEST_SYSTEM_USER_DICT, TEST_SUPERUSER_DICT]
}

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

_EXTRA_PROJECT_DEFAULTS = {
    "resource_ids": [],
    "source": "internal",
    "user_emails": None,
    "admin_email": None,
}
_PAGINATION: List["_PaginationInfo"] = load_json_fixture("pagination.json")
T = TypeVar("T")


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
        assert get_db_record(db, UserRequest, _filter=filter_obj) is None

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
        }
        assert isinstance(got.pop("id"), str)
        assert response.status_code == 201
        assert got == expected
        assert get_db_record(db, UserRequest, _filter=filter_obj) is not None


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
        assert get_db_record(db, UserRequest, _filter=filter_obj) is None


@pytest.mark.parametrize("project", PROJECT_LIST)
def test_unauthenticated_create_qpu_time_user_request(
    project, client, inserted_project_ids, db
):
    """Unauthenticated users can not create a user request at /admin/qpu-time-requests/"""
    # using context manager to ensure on_startup runs
    with client as client:
        request_body = {**_QPU_TIME_REQUEST, "project_id": project["_id"]}
        filter_obj = {"request.project_id": request_body["project_id"]}
        assert get_db_record(db, UserRequest, _filter=filter_obj) is None

        response = client.post("/admin/qpu-time-requests/", json=request_body)

        got = response.json()
        assert response.status_code == 401
        assert got == {"detail": "Unauthorized"}
        assert get_db_record(db, UserRequest, _filter=filter_obj) is None


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
        original_user_request = get_db_record(db, UserRequest, user_request_id)
        response = client.put(
            f"/admin/user-requests/{user_request_id}",
            cookies=user_jwt_cookie,
            json=payload,
        )

        got = response.json()
        updated_user_request = get_db_record(db, UserRequest, user_request_id)

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
        original_user_request = get_db_record(db, UserRequest, user_request_id)
        response = client.put(
            f"/admin/user-requests/{user_request_id}",
            cookies=admin_jwt_cookie,
            json=payload,
        )

        got = response.json()
        updated_user_request = get_db_record(db, UserRequest, user_request_id)

        assert response.status_code == 404
        assert got == {"detail": f"{user_request_id} not found"}
        assert updated_user_request == original_user_request


# TODO: test for other user request types


@pytest.mark.parametrize("project", _PROJECT_CREATE_LIST)
def test_admin_create_project(db, project, client, admin_jwt_cookie, freezer):
    """Admins can create projects at /admin/projects/"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post(
            "/admin/projects/", json=project, cookies=admin_jwt_cookie
        )

        got = response.json()
        assert response.status_code == 201
        now = get_timestamp_str(datetime.now(timezone.utc))

        user_emails = [*project["user_emails"]]
        if project["admin_email"] not in user_emails:
            user_emails.append(project["admin_email"])

        users = find_in_collection(
            db, "auth_users", _filter={"email": {"$in": user_emails}}
        )
        user_email_id_map = {v["email"]: str(v["_id"]) for v in users}
        user_ids = [user_email_id_map[k] for k in user_emails]
        admin_id = user_email_id_map[project["admin_email"]]

        expected = {
            "id": got["id"],
            "ext_id": project["ext_id"],
            "is_active": True,
            "qpu_seconds": project.get("qpu_seconds", 0),
            "name": project["name"],
            "description": project["description"],
            "user_ids": user_ids,
            "admin_id": admin_id,
            "admin_email": project["admin_email"],
            "user_emails": user_emails,
            "created_at": now,
            "updated_at": now,
        }
        assert got == expected


@pytest.mark.parametrize("project", _PROJECT_CREATE_LIST)
def test_non_admin_cannot_create_project(project, client, user_jwt_cookie):
    """Non-admins cannot create projects at /admin/projects"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post(
            "/admin/projects/", json=project, cookies=user_jwt_cookie
        )

        got = response.json()
        assert response.status_code == 403
        expected = {"detail": "Forbidden"}
        assert got == expected


@pytest.mark.parametrize("payload", _PROJECT_UPDATE_LIST)
def test_admin_update_project(db, payload, client, admin_jwt_cookie, freezer):
    """Admins can update projects at /admin/projects/{id}"""
    payload = copy.deepcopy(payload)
    created_at = get_timestamp_str(datetime.now(timezone.utc))
    # using context manager to ensure on_startup runs
    with client as client:
        post_body = _PROJECT_CREATE_LIST[0]
        response = client.post(
            "/admin/projects/", json=post_body, cookies=admin_jwt_cookie
        )
        assert response.status_code == 201
        project = response.json()
        _id = project["id"]

        freezer.move_to("2024-05-20")
        updated_at = get_timestamp_str(datetime.now(timezone.utc))
        url = f"/admin/projects/{_id}"
        response = client.put(url, json=payload, cookies=admin_jwt_cookie)

        new_user_emails = [*payload.get("user_emails", [])]
        is_admin_to_change = "admin_email" in payload
        if is_admin_to_change:
            new_user_emails.append(payload["admin_email"])

        users = find_in_collection(
            db,
            "auth_users",
            _filter={
                "$or": [
                    {"email": {"$in": new_user_emails}},
                    {"_id": {"$in": project["user_ids"]}},
                ]
            },
        )
        user_email_id_map = {v["email"]: str(v["_id"]) for v in users}
        admin_email = payload.get("admin_email", project.get("admin_email"))
        user_ids = project["user_ids"]
        admin_id = user_email_id_map.get(admin_email, project["admin_id"])
        user_id_email_map = {v: k for k, v in user_email_id_map.items()}
        user_id_email_map[admin_id] = admin_email

        if "user_emails" in payload:
            # the user_ids and user_emails have been updated
            user_ids = [user_email_id_map[k] for k in payload["user_emails"]]

        if admin_id not in user_ids:
            # admin id should always be in the user ids
            user_ids.append(admin_id)

        expected = {
            "id": _id,
            "ext_id": project["ext_id"],
            "is_active": payload.get("is_active", project["is_active"]),
            "qpu_seconds": payload.get("qpu_seconds", project["qpu_seconds"]),
            "name": payload.get("name", project["name"]),
            "description": payload.get("description", project["description"]),
            "user_ids": user_ids,
            "admin_id": admin_id,
            "admin_email": payload.get("admin_email", project["admin_email"]),
            "user_emails": [user_id_email_map[v] for v in user_ids],
            "created_at": created_at,
            "updated_at": updated_at,
        }

        got = response.json()
        assert response.status_code == 200
        assert got == expected
        assert updated_at != created_at


@pytest.mark.parametrize("payload", _PROJECT_UPDATE_LIST)
def test_non_admin_cannot_update_project(payload, client, user_jwt_cookie):
    """Non-admins cannot create projects at /admin/projects/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        url = f"/admin/projects/{TEST_PROJECT_ID}"
        response = client.put(url, json=payload, cookies=user_jwt_cookie)

        got = response.json()
        assert response.status_code == 403
        expected = {"detail": "Forbidden"}
        assert got == expected


def test_admin_view_all_projects_in_detail(
    client, inserted_project_ids, admin_jwt_cookie, freezer
):
    """Admins can view projects at /admin/projects/ in full detail"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/admin/projects/", cookies=admin_jwt_cookie)

        got = response.json()
        project_list = [
            {
                "id": str(item["_id"]),
                "ext_id": item["ext_id"],
                "qpu_seconds": item["qpu_seconds"],
                "is_active": item.get("is_active", True),
                "user_ids": item.get("user_ids"),
                "admin_id": item.get("admin_id"),
                "admin_email": USER_ID_EMAIL_MAP.get(item.get("admin_id")),
                "user_emails": [
                    USER_ID_EMAIL_MAP.get(v) for v in item.get("user_ids", [])
                ],
                "name": item.get("name"),
                "description": item.get("description"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }
            for item in [TEST_PROJECT_DICT, TEST_NO_QPU_PROJECT_DICT] + PROJECT_LIST
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": project_list}


@pytest.mark.parametrize("project", PROJECT_LIST)
def test_non_admin_cannot_view_all_projects_in_detail(
    project, db, client, inserted_project_ids, user_jwt_cookie
):
    """Non-admins cannot view projects at /admin/projects/"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/admin/projects/", cookies=user_jwt_cookie)

        got = response.json()
        expected = {"detail": "Forbidden"}
        assert response.status_code == 403
        assert got == expected


@pytest.mark.parametrize("project", PROJECT_LIST)
def test_admin_view_single_project_in_detail(
    project, client, inserted_projects, admin_jwt_cookie, freezer
):
    """Admins can view single project at /admin/projects/{id} in full detail"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = project["_id"]
        url = f"/admin/projects/{_id}"
        response = client.get(url, cookies=admin_jwt_cookie)

        got = response.json()
        expected = {
            "id": _id,
            "ext_id": project["ext_id"],
            "qpu_seconds": project["qpu_seconds"],
            "is_active": project["is_active"],
            "user_ids": project.get("user_ids"),
            "admin_id": project.get("admin_id"),
            "admin_email": USER_ID_EMAIL_MAP.get(project.get("admin_id")),
            "user_emails": [
                USER_ID_EMAIL_MAP.get(v) for v in project.get("user_ids", [])
            ],
            "name": project.get("name"),
            "description": project.get("description"),
            "created_at": project.get("created_at"),
            "updated_at": project.get("updated_at"),
        }

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("project", PROJECT_LIST)
def test_non_admin_cannot_view_single_project_in_detail(
    project, db, client, inserted_project_ids, user_jwt_cookie
):
    """Non-admins cannot view single project at /admin/projects/{_id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = project["_id"]
        url = f"/admin/projects/{_id}"
        response = client.get(url, cookies=user_jwt_cookie)

        got = response.json()
        expected = {"detail": "Forbidden"}
        assert response.status_code == 403
        assert got == expected


@pytest.mark.parametrize("project", PROJECT_LIST)
def test_admin_delete_project(
    project, db, client, inserted_project_ids, admin_jwt_cookie, freezer
):
    """Admins can delete projects at /admin/projects/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = project["_id"]
        original = get_db_record(db, Project, _id)
        assert original is not None

        url = f"/admin/projects/{_id}"
        response = client.delete(url, cookies=admin_jwt_cookie)

        now = get_timestamp_str(datetime.now(timezone.utc))
        deleted_project = get_db_record(db, DeletedProject, _id)
        pruned_fields = ["created_at", "updated_at"]
        pruned_deleted_project, deleted_project_timestamps = prune(
            deleted_project, pruned_fields
        )
        pruned_original, _ = prune(original, pruned_fields)
        pruned_original.update(_EXTRA_PROJECT_DEFAULTS)

        assert response.status_code == 204
        assert get_db_record(db, Project, _id) is None
        assert pruned_deleted_project == pruned_original
        for timestamp in deleted_project_timestamps.values():
            assert timestamp == now


@pytest.mark.parametrize("project", PROJECT_LIST)
def test_non_admin_cannot_delete_project(
    project, db, client, inserted_project_ids, user_jwt_cookie
):
    """Non-admins cannot delete projects at /admin/projects/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = project["_id"]
        assert get_db_record(db, Project, _id) is not None

        url = f"/admin/projects/{_id}"
        response = client.delete(url, cookies=user_jwt_cookie)

        got = response.json()
        expected = {"detail": "Forbidden"}
        assert response.status_code == 403
        assert got == expected
        assert get_db_record(db, Project, _id) is not None


@pytest.mark.parametrize("pagination", _PAGINATION)
def test_admin_view_users(client, admin_jwt_cookie, user_jwt_cookie, pagination):
    """GET '/admin/bcc-users/{backend}' should show to an admin the paginated list of user profiles via MSS"""
    with client as client:
        # non admins are not allowed
        response = client.get("/admin/bcc-users/loke/", cookies=user_jwt_cookie)
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.get("/admin/bcc-users/loke/", cookies=admin_jwt_cookie)
        actual_output = response.json()

        skip = pagination["skip"]
        limit = pagination["limit"]

        users = [TEST_USER_DICT, TEST_SYSTEM_USER_DICT, TEST_SUPERUSER_DICT]
        expected = _paginate(users, skip=skip, limit=limit)

        assert response.status_code == 200
        assert actual_output == expected


# @pytest.mark.parametrize("client, redis_conn, worker, job", _SIMPLE_UPLOAD_JOB_PARAMS)
# def test_admin_remove_user(
#     client, worker, redis_conn, job, jobs_folder, mocker: MockerFixture
# ):
#     """DELETE '/users/{user_id}' by admin removes the user, and their bookings and jobs"""
#     with client as client:
#         users = [curr_user, other_user] = _create_many_users(client, USERS[:2])
#         curr_user_id = curr_user["id"]
#         other_user_id = other_user["id"]
#
#         # create many bookings for this user
#         for booking in VALID_BOOKINGS[:TEST_MAX_SLOTS_PER_DAY]:
#             _, result = _create_booking(client, user_id=curr_user_id, booking=booking)
#
#         # create a booking for other user
#         _create_booking(
#             client, user_id=other_user_id, booking={"starts_in": 8, "duration": 2}
#         )
#
#         # wait for the first booking to start
#         raw_jobs = _get_raw_jobs(job, durations=[0.23, 0.1, 0.23])
#         job_metadata_list = _get_job_submission_metadata(
#             client, jobs=raw_jobs, users=users, mocker=mocker, jobs_folder=jobs_folder
#         )
#         _submit_multiple_jobs_v2(
#             client,
#             data=job_metadata_list,
#         )
#
#         # This also removes the user's pending bookings,
#         # and cancels their pending jobs
#         response = _remove_user(
#             client, current_user_id=other_user_id, user_id=curr_user_id, is_admin=True
#         )
#         assert response.status_code == 200
#         assert response.json() == {"status": "success", "detail": f"User deleted"}
#
#         response = _view_own_profile(client, user_id=curr_user_id)
#         assert response.status_code == 404
#         assert response.json() == {"detail": "user not found"}
#
#         # Run the queue; try to wait for waitlist to transfer things to execution queue
#         _wait_on_rq_worker(worker, with_scheduler=True)
#
#         jobs_in_redis = _get_jobs_in_redis(redis_conn)
#
#         deleted_user_jobs = [
#             job for job in jobs_in_redis if job.user_id == curr_user_id
#         ]
#         other_user_jobs = [job for job in jobs_in_redis if job.user_id != curr_user_id]
#         failure_reason = "Cancelled on user deletion"
#
#         assert all([v.status == JobStatus.CANCELLED for v in deleted_user_jobs])
#         assert all([v.failure_reason == failure_reason for v in deleted_user_jobs])
#         assert all([v.status == JobStatus.SUCCESSFUL for v in other_user_jobs])
#
#
# @pytest.mark.parametrize(
#     "client, redis_conn, worker, job", _SIMPLE_UPLOAD_JOB_PARAMS[:-1]
# )
# def test_non_admin_remove_user(
#     client, worker, redis_conn, job, jobs_folder, mocker: MockerFixture
# ):
#     """Non admin cannot remove the profile of any user"""
#     with client as client:
#         users = [curr_user, other_user] = _create_many_users(client, USERS[:2])
#         curr_user_id = curr_user["id"]
#         other_user_id = other_user["id"]
#
#         # create many bookings for this user
#         for booking in VALID_BOOKINGS[:TEST_MAX_SLOTS_PER_DAY]:
#             _, result = _create_booking(client, user_id=curr_user_id, booking=booking)
#
#         raw_jobs = _get_raw_jobs(job, durations=[0.23, 0.4, 0.3])
#         job_metadata_list = _get_job_submission_metadata(
#             client, jobs=raw_jobs, users=users, mocker=mocker, jobs_folder=jobs_folder
#         )
#         _submit_multiple_jobs_v2(client, data=job_metadata_list)
#
#         # Non-admins fail
#         for user_id in (curr_user_id, other_user_id):
#             response = _remove_user(
#                 client, current_user_id=user_id, user_id=curr_user_id
#             )
#             assert response.status_code == 403
#             assert response.json() == {"detail": "Forbidden"}
#
#         response = _view_own_profile(client, user_id=curr_user_id)
#         assert response.status_code == 200
#
#         # Run the queue; try to wait for waitlist to transfer things to execution queue
#         _wait_on_rq_worker(worker, with_scheduler=True)
#
#         jobs_in_redis = _get_jobs_in_redis(redis_conn)
#         assert all([v.status == JobStatus.SUCCESSFUL for v in jobs_in_redis])


def _db_to_http_item(db_item: Dict[str, Any]) -> Dict[str, Any]:
    """Converts a database item into an item that can be expected to be returned by HTTP server

    Args:
        db_item: the item in the database

    Returns:
        the item as would be seen from an HTTP response
    """
    item = copy.deepcopy(db_item)
    item["id"] = str(item.pop("_id"))
    return item


def _paginate(
    data: List[T], skip: int = 0, limit: Optional[int] = None
) -> "_PaginatedList[T]":
    """Paginates the data basing on the skip and the limit params

    Args:
        skip: the number of records to skip
        limit: the maximum number of records to return

    Returns:
        list of the data sliced according to the pagination info
    """
    slice_limit = limit
    if isinstance(slice_limit, int):
        slice_limit += skip
    return {"skip": skip, "limit": limit, "data": data[skip:slice_limit]}


class _PaginationInfo(TypedDict):
    """The pagination info"""

    skip: int
    limit: Optional[float]


class _PaginatedList(TypedDict, Generic[T]):
    """The type for paginated responses"""

    skip: int
    limit: Optional[int]
    data: List[T]
