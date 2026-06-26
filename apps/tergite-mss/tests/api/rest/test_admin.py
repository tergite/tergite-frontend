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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest
from bson import ObjectId
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
    TEST_SUPERUSER_EMAIL,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_DICT,
    TEST_SYSTEM_USER_ID,
    TEST_USER_DICT,
    TEST_USER_EMAIL,
    TEST_USER_ID,
    USER_ID_EMAIL_MAP,
    get_db_record,
)
from ..._utils.date_time import get_timestamp_str
from ..._utils.fixtures import load_json_fixture
from ..._utils.mock_backend import BCC_USERS
from ..._utils.mongodb import find_in_collection, insert_in_collection
from ..._utils.records import paginate, prune, with_offset_datetimes
from ...conftest import BACKEND_SLUGS, PROJECT_LIST, get_auth_cookie

_REQ_STATUSES = ["pending", "rejected", "approved"]
_USER_REQUEST_COLLECTION = "auth_user_requests"
_USER_REQUESTS_IN_DB = load_json_fixture("user_requests.json")
_PROJECT_CREATE_LIST = load_json_fixture("project_create_list.json")
_PROJECT_UPDATE_LIST = load_json_fixture("project_update_list.json")
_BCC_USERS = load_json_fixture("bcc_users.json")

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
_PAGINATION: List["PaginationInfo"] = load_json_fixture("pagination.json")

_BCC_USERS_VIEW_PARAMS = [
    (backend, pagination) for backend in BACKEND_SLUGS for pagination in _PAGINATION
]
_BCC_USERS_CREATE_PARAMS = [
    (backend, payload) for backend in BACKEND_SLUGS for payload in _BCC_USERS
]
T = TypeVar("T")

# ── Notices ──────────────────────────────────────────────────────────────────

_NOTICES_COLLECTION = "notices"
_NOTICES_IN_DB_RAW = load_json_fixture("notices.json")

# IDs of the notices in the fixture (mirrors the _id fields in notices.json)
_NOTICE_TARGETING_ADMIN_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"
_NOTICE_TARGETING_USER_ID = "bbbbbbbbbbbbbbbbbbbbbbbb"
_NOTICE_BROADCAST_ID = "cccccccccccccccccccccccc"
_NOTICE_DISMISSED_BY_USER_ID = "dddddddddddddddddddddddd"
_NOTICE_FUTURE_ID = "eeeeeeeeeeeeeeeeeeeeeeee"

# Individual raw fixture dicts for tests that need to insert a single notice
_NOTICE_TARGETING_ADMIN_RAW = next(
    n for n in _NOTICES_IN_DB_RAW if n["_id"] == _NOTICE_TARGETING_ADMIN_ID
)
_NOTICE_TARGETING_USER_RAW = next(
    n for n in _NOTICES_IN_DB_RAW if n["_id"] == _NOTICE_TARGETING_USER_ID
)
_NOTICE_BROADCAST_RAW = next(
    n for n in _NOTICES_IN_DB_RAW if n["_id"] == _NOTICE_BROADCAST_ID
)
_NOTICE_DISMISSED_BY_USER_RAW = next(
    n for n in _NOTICES_IN_DB_RAW if n["_id"] == _NOTICE_DISMISSED_BY_USER_ID
)
_NOTICE_FUTURE_RAW = next(
    n for n in _NOTICES_IN_DB_RAW if n["_id"] == _NOTICE_FUTURE_ID
)


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


@pytest.mark.parametrize("backend, user_payload", _BCC_USERS_CREATE_PARAMS)
def test_admin_create_bcc_user(
    client, backend, user_payload, user_jwt_cookie, admin_jwt_cookie, mock_bcc
):
    """POST to '/admin/bcc-users' by admins should create the user via MSS"""
    with client as client:
        payload = {**user_payload, "id": TEST_USER_ID}
        # non admins are not allowed
        response = client.post(
            f"/admin/bcc-users/{backend}", cookies=user_jwt_cookie, json=payload
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.post(
            f"/admin/bcc-users/{backend}", cookies=admin_jwt_cookie, json=payload
        )
        expected = {
            "id": TEST_USER_ID,
            "name": user_payload["name"],
            "email": user_payload["email"],
            "is_admin": False,
        }

        assert response.status_code == 200
        assert response.json() == expected


@pytest.mark.parametrize("backend, pagination", _BCC_USERS_VIEW_PARAMS)
def test_admin_view_bcc_users(
    client, admin_jwt_cookie, user_jwt_cookie, backend, pagination, mock_bcc
):
    """GET '/admin/bcc-users/{backend}' should show to an admin the paginated list of user profiles via MSS"""
    with client as client:
        params = {k: v for k, v in pagination.items() if v is not None}
        # non admins are not allowed
        response = client.get(
            f"/admin/bcc-users/{backend}/", cookies=user_jwt_cookie, params=params
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.get(
            f"/admin/bcc-users/{backend}/", cookies=admin_jwt_cookie, params=params
        )
        actual_output = response.json()

        skip = pagination["skip"]
        limit = pagination["limit"]

        expected = paginate(BCC_USERS, skip=skip, limit=limit)

        assert response.status_code == 200
        assert actual_output == expected


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_remove_bcc_user(client, backend, admin_jwt_cookie, mock_bcc):
    """DELETE '/admin/bcc-users/{backend}/{user_id}' by admin removes the user via MSS"""
    with client as client:
        url = f"/admin/bcc-users/{backend}/USER_ID_PLACEHOLDER"
        response = client.delete(url, cookies=admin_jwt_cookie)
        assert response.status_code == 200
        assert response.json() == {"status": "success", "detail": f"User deleted"}


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_non_admin_remove_user(client, backend, user_jwt_cookie, mock_bcc):
    """Non admin cannot remove the profile of any user"""
    with client as client:
        url = f"/admin/bcc-users/{backend}/USER_ID_PLACEHOLDER"
        response = client.delete(url, cookies=user_jwt_cookie)
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_init_recalibration(
    client, admin_jwt_cookie, user_jwt_cookie, backend, mock_bcc
):
    """POST '/admin/recalibration/{backend}/init' should start recalibration via MSS"""
    with client as client:
        params = {
            "interval": 3000,
            "start_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # non admins are not allowed
        response = client.post(
            f"/admin/recalibration/{backend}/init",
            cookies=user_jwt_cookie,
            params=params,
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.post(
            f"/admin/recalibration/{backend}/init",
            cookies=admin_jwt_cookie,
            params=params,
        )
        actual_output = response.json()

        assert response.status_code == 200
        assert actual_output == {"status": "success"}


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_get_recalibration_info(
    client,
    admin_jwt_cookie,
    user_jwt_cookie,
    backend,
    mock_bcc,
):
    """GET '/admin/recalibration/{backend}/info' should get recalibration info via MSS"""
    with client as client:
        # non admins are not allowed
        response = client.get(
            f"/admin/recalibration/{backend}/info", cookies=user_jwt_cookie
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.get(
            f"/admin/recalibration/{backend}/info", cookies=admin_jwt_cookie
        )
        actual_output = response.json()

        assert response.status_code == 200
        assert actual_output == {
            "current_job_id": None,
            "current_job_status": None,
            "current_job_started_at": None,
            "previous_job_id": "last_finished_rq_job_id",
            "previous_job_status": "finished",
            "previous_job_started_at": "2026-04-27T00:00:25.495000Z",
            "previous_job_ended_at": "2026-04-27T00:00:25.495000Z",
            "previous_job_error": None,
            "next_job_id": "next_rq_job_id",
            "next_job_status": "scheduled",
            "next_job_enqueued_at": None,
            "interval": 4000.0,
        }


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_cancel_recalibration(
    client, admin_jwt_cookie, user_jwt_cookie, backend, mock_bcc
):
    """POST '/admin/recalibration/{backend}/cancel' should stop recalibration via MSS"""
    with client as client:
        params = {
            "ignore_errors": True,
        }
        # non admins are not allowed
        response = client.post(
            f"/admin/recalibration/{backend}/cancel",
            cookies=user_jwt_cookie,
            params=params,
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.post(
            f"/admin/recalibration/{backend}/cancel",
            cookies=admin_jwt_cookie,
            params=params,
        )
        actual_output = response.json()

        assert response.status_code == 200
        assert actual_output == {"status": "success"}


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_switch_off(client, admin_jwt_cookie, user_jwt_cookie, backend, mock_bcc):
    """POST '/admin/switch/{backend}/off' switches off the backend via MSS"""
    with client as client:
        # non admins are not allowed
        response = client.post(f"/admin/switch/{backend}/off", cookies=user_jwt_cookie)
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.post(f"/admin/switch/{backend}/off", cookies=admin_jwt_cookie)
        actual_output = response.json()

        assert response.status_code == 200
        assert actual_output == {"status": "success"}


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_switch_on(client, admin_jwt_cookie, user_jwt_cookie, backend, mock_bcc):
    """POST '/admin/switch/{backend}/on' switches on the backend via MSS"""
    with client as client:
        # non admins are not allowed
        response = client.post(f"/admin/switch/{backend}/on", cookies=user_jwt_cookie)
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.post(f"/admin/switch/{backend}/on", cookies=admin_jwt_cookie)
        actual_output = response.json()

        assert response.status_code == 200
        assert actual_output == {"status": "success"}


def test_admin_publish_notice(admin_jwt_cookie, client, db):
    """Admin can publish a notice via POST /admin/notices/"""
    payload = {
        "message": "Important maintenance window",
        "severity": "warning",
        "starts_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
    }
    with client as client:
        response = client.post(
            "/admin/notices/", cookies=admin_jwt_cookie, json=payload
        )
        got = response.json()

        assert response.status_code == 200
        assert isinstance(got["id"], str)
        assert got["message"] == payload["message"]
        assert got["severity"] == payload["severity"]
        assert got["created_by"] == TEST_SUPERUSER_ID
        assert got["target_user_ids"] is None
        assert got["dismissed_by"] == []

        # verify notice was persisted to db
        notices = find_in_collection(db, _NOTICES_COLLECTION)
        assert len(notices) == 1
        assert str(notices[0]["_id"]) == got["id"]


def test_admin_publish_notice_with_target_emails(admin_jwt_cookie, client, db):
    """Admin can publish a targeted notice via POST /admin/notices/ with target_user_emails"""
    payload = {
        "message": "Notice for specific users",
        "severity": "info",
        "starts_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
        "target_user_emails": [TEST_USER_EMAIL, TEST_SUPERUSER_EMAIL],
    }
    with client as client:
        response = client.post(
            "/admin/notices/", cookies=admin_jwt_cookie, json=payload
        )
        got = response.json()

        assert response.status_code == 200
        assert isinstance(got["id"], str)
        assert got["target_user_ids"] is not None
        assert len(got["target_user_ids"]) == 2
        assert TEST_USER_ID in got["target_user_ids"]
        assert TEST_SUPERUSER_ID in got["target_user_ids"]


def test_non_admin_publish_notice(user_jwt_cookie, client, db):
    """Non-admin cannot publish a notice via POST /admin/notices/"""
    payload = {
        "message": "Should not be created",
        "severity": "info",
        "starts_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
    }
    with client as client:
        response = client.post("/admin/notices/", cookies=user_jwt_cookie, json=payload)
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}
        assert find_in_collection(db, _NOTICES_COLLECTION) == []


def test_unauthenticated_publish_notice(client, db):
    """Unauthenticated users cannot publish a notice via POST /admin/notices/"""
    payload = {
        "message": "Should not be created",
        "severity": "info",
        "starts_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
    }
    with client as client:
        response = client.post("/admin/notices/", json=payload)
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
        assert find_in_collection(db, _NOTICES_COLLECTION) == []


def test_admin_delete_notice(admin_jwt_cookie, client, db):
    """Admin can delete a notice via DELETE /admin/notices/{notice_id}"""
    _insert_notices(db, [_NOTICE_TARGETING_ADMIN_RAW])

    with client as client:
        assert len(find_in_collection(db, _NOTICES_COLLECTION)) == 1

        response = client.delete(
            f"/admin/notices/{_NOTICE_TARGETING_ADMIN_ID}", cookies=admin_jwt_cookie
        )
        got = response.json()

        assert response.status_code == 200
        assert got["id"] == _NOTICE_TARGETING_ADMIN_ID
        assert got["message"] == _NOTICE_TARGETING_ADMIN_RAW["message"]
        assert find_in_collection(db, _NOTICES_COLLECTION) == []


def test_non_admin_delete_notice(user_jwt_cookie, client, db):
    """Non-admin cannot delete a notice via DELETE /admin/notices/{notice_id}"""
    _insert_notices(db, [_NOTICE_TARGETING_ADMIN_RAW])

    with client as client:
        response = client.delete(
            f"/admin/notices/{_NOTICE_TARGETING_ADMIN_ID}", cookies=user_jwt_cookie
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}
        assert len(find_in_collection(db, _NOTICES_COLLECTION)) == 1


def test_delete_non_existent_notice(admin_jwt_cookie, client, db):
    """DELETE /admin/notices/{notice_id} returns 404 when the notice does not exist"""
    with client as client:
        response = client.delete(
            f"/admin/notices/{_NOTICE_TARGETING_ADMIN_ID}", cookies=admin_jwt_cookie
        )
        assert response.status_code == 404


def test_any_user_can_dismiss_notice(user_jwt_cookie, client, db):
    """Any authenticated user can dismiss a notice via POST /admin/notices/{notice_id}/dismiss"""
    _insert_notices(db, [_NOTICE_TARGETING_USER_RAW])

    with client as client:
        response = client.post(
            f"/admin/notices/{_NOTICE_TARGETING_USER_ID}/dismiss",
            cookies=user_jwt_cookie,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        # TEST_USER_ID should now be in the dismissed_by list
        notices = find_in_collection(db, _NOTICES_COLLECTION)
        assert len(notices) == 1
        dismissed_by_strs = [str(oid) for oid in notices[0]["dismissed_by"]]
        assert TEST_USER_ID in dismissed_by_strs


def test_admin_can_dismiss_notice(admin_jwt_cookie, client, db):
    """Admin can also dismiss a notice via POST /admin/notices/{notice_id}/dismiss"""
    _insert_notices(db, [_NOTICE_TARGETING_ADMIN_RAW])

    with client as client:
        response = client.post(
            f"/admin/notices/{_NOTICE_TARGETING_ADMIN_ID}/dismiss",
            cookies=admin_jwt_cookie,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        notices = find_in_collection(db, _NOTICES_COLLECTION)
        dismissed_by_strs = [str(oid) for oid in notices[0]["dismissed_by"]]
        assert TEST_SUPERUSER_ID in dismissed_by_strs


def test_unauthenticated_dismiss_notice(client, db):
    """Unauthenticated users cannot dismiss a notice"""
    _insert_notices(db, [_NOTICE_TARGETING_USER_RAW])

    with client as client:
        response = client.post(f"/admin/notices/{_NOTICE_TARGETING_USER_ID}/dismiss")
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

        # notice should remain unchanged
        notices = find_in_collection(db, _NOTICES_COLLECTION)
        assert notices[0]["dismissed_by"] == []


def test_dismiss_non_existent_notice(user_jwt_cookie, client, db):
    """POST /admin/notices/{notice_id}/dismiss returns 404 when notice does not exist"""
    with client as client:
        response = client.post(
            f"/admin/notices/{_NOTICE_TARGETING_USER_ID}/dismiss",
            cookies=user_jwt_cookie,
        )
        assert response.status_code == 404


def test_admin_get_all_notices(admin_jwt_cookie, client, db):
    """Admin with no user_id filter retrieves all notices via GET /admin/notices"""
    _insert_notices(db, _NOTICES_IN_DB_RAW)

    with client as client:
        response = client.get("/admin/notices", cookies=admin_jwt_cookie)
        got = response.json()

        assert response.status_code == 200
        assert got["skip"] == 0
        assert got["limit"] is None
        assert len(got["data"]) == len(_NOTICES_IN_DB_RAW)


def test_admin_get_notices_filtered_by_user_id(admin_jwt_cookie, client, db):
    """Admin can filter notices by user_id via GET /admin/notices?user_id=...

    When include_dismissed=true, both active and dismissed notices for the user are returned.
    Only notices with target_user_ids containing the user_id or those with no target_user_ids are matched.
    """
    _insert_notices(db, _NOTICES_IN_DB_RAW)
    expected_ids = {
        n["_id"]
        for n in _NOTICES_IN_DB_RAW
        if (n["target_user_ids"] and TEST_USER_ID in n["target_user_ids"])
        or (n["target_user_ids"] is None)
    }

    with client as client:
        response = client.get(
            f"/admin/notices?user_id={TEST_USER_ID}&include_dismissed=true",
            cookies=admin_jwt_cookie,
        )
        got = response.json()

        assert response.status_code == 200
        returned_ids = {n["id"] for n in got["data"]}
        assert returned_ids == expected_ids


def test_admin_get_notices_excludes_dismissed_by_default(admin_jwt_cookie, client, db):
    """GET /admin/notices?user_id=... excludes dismissed notices unless include_dismissed=true"""
    _insert_notices(db, _NOTICES_IN_DB_RAW)

    with client as client:
        response = client.get(
            f"/admin/notices?user_id={TEST_USER_ID}",
            cookies=admin_jwt_cookie,
        )
        got = response.json()

        assert response.status_code == 200
        returned_ids = {n["id"] for n in got["data"]}
        assert _NOTICE_TARGETING_USER_ID in returned_ids
        assert _NOTICE_DISMISSED_BY_USER_ID not in returned_ids


def test_non_admin_get_notices_forced_to_own_user_id(user_jwt_cookie, client, db):
    """Non-admin is forced to use their own user_id when calling GET /admin/notices

    Even if a different user_id is provided in the query, the non-admin only sees
    notices that target themselves (not dismissed) and broadcast notices
    (i.e. no target_user_ids).
    """
    _insert_notices(db, _NOTICES_IN_DB_RAW)

    with client as client:
        # Non-admin tries to request admin's notices — should be ignored
        response = client.get(
            f"/admin/notices?user_id={TEST_SUPERUSER_ID}",
            cookies=user_jwt_cookie,
        )
        got = response.json()

        assert response.status_code == 200
        returned_ids = {n["id"] for n in got["data"]}
        # Should see own non-dismissed targeted notices
        assert _NOTICE_TARGETING_USER_ID in returned_ids
        # Should not see admin's notices, dismissed notices, or broadcast
        assert _NOTICE_TARGETING_ADMIN_ID not in returned_ids
        assert _NOTICE_DISMISSED_BY_USER_ID not in returned_ids
        # Broadcast (target_user_ids=None) are returned when user_id filter applies
        assert _NOTICE_BROADCAST_ID in returned_ids


def test_unauthenticated_get_notices(client, db):
    """Unauthenticated users cannot access GET /admin/notices"""
    _insert_notices(db, _NOTICES_IN_DB_RAW)

    with client as client:
        response = client.get("/admin/notices")
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


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


def _insert_notices(
    db, notices_raw: List[Dict[str, Any]], now: datetime = None
) -> None:
    """Inserts notices into the database, converting offset hours to datetimes and IDs to ObjectId

    Args:
        db: the mongodb database
        notices_raw: list of raw notice dicts from the fixture (with offset_hours fields)
        now: reference datetime for offset conversion; defaults to UTC now
    """
    if now is None:
        now = datetime.now(timezone.utc)

    records = with_offset_datetimes(
        notices_raw,
        {
            "starts_at": "starts_at_offset_hours",
            "expires_at": "expires_at_offset_hours",
        },
        now=now,
    )

    def _convert(k: str, v: Any) -> Any:
        if v is None:
            return None
        if k in ("_id", "created_by"):
            return ObjectId(v)
        if k in ("target_user_ids", "dismissed_by") and isinstance(v, list):
            return [ObjectId(i) for i in v]
        return v

    db[_NOTICES_COLLECTION].insert_many(
        [{k: _convert(k, v) for k, v in record.items()} for record in records]
    )
