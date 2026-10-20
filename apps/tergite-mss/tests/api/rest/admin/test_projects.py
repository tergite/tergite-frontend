# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2024, 2026
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

import pytest

from services.auth import DeletedProject, Project
from services.notices import NoticeType
from tests._utils.auth import (
    TEST_NO_QPU_PROJECT_DICT,
    TEST_OUTSIDER_EMAIL,
    TEST_OUTSIDER_ID,
    TEST_PROJECT_DICT,
    TEST_PROJECT_ID,
    TEST_PROJECT_NAME,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_EMAIL,
    TEST_SYSTEM_USER_ID,
    TEST_USER_EMAIL,
    TEST_USER_ID,
    USER_ID_EMAIL_MAP,
    get_db_record,
)
from tests._utils.date_time import get_timestamp_str
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import find_in_collection
from tests._utils.notices import get_user_notices
from tests._utils.records import prune
from tests.conftest import PROJECT_LIST

_PROJECT_CREATE_LIST = load_json_fixture("project_create_list.json")
_PROJECT_UPDATE_LIST = load_json_fixture("project_update_list.json")
_EXTRA_PROJECT_DEFAULTS = {"is_personal": False}
_NOTIFIED_PROJECT = {
    "admin_email": TEST_USER_EMAIL,
    "user_emails": [TEST_OUTSIDER_EMAIL],
    "name": "notified project",
    "description": "a project whose members hear about it",
    "qpu_seconds": 100,
}
_ALL_PROJECTS = [TEST_PROJECT_DICT, TEST_NO_QPU_PROJECT_DICT] + PROJECT_LIST
_PROJECT_QUERIES = [
    ([("is_active", "false")], lambda v: not v.get("is_active", True)),
    (
        [("min_qpu_seconds", "0"), ("max_qpu_seconds", "60000")],
        lambda v: 0 <= v["qpu_seconds"] <= 60000,
    ),
    (
        [("name", "Normal Test"), ("name", "Zero QPU")],
        lambda v: v["name"] in ("Normal Test", "Zero QPU"),
    ),
    (
        [("id", TEST_PROJECT_ID), ("id", "7c445113e77284cef9397c5b")],
        lambda v: str(v["_id"]) in (TEST_PROJECT_ID, "7c445113e77284cef9397c5b"),
    ),
    (
        [("user_ids", TEST_SUPERUSER_ID)],
        lambda v: TEST_SUPERUSER_ID in [str(u) for u in v["user_ids"]],
    ),
]


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
            "is_active": True,
            "qpu_seconds": project.get("qpu_seconds", 0),
            "name": project["name"],
            "description": project["description"],
            "user_ids": user_ids,
            "admin_id": admin_id,
            "admin_email": project["admin_email"],
            "user_emails": user_emails,
            "is_personal": False,
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
            "is_active": payload.get("is_active", project["is_active"]),
            "qpu_seconds": payload.get("qpu_seconds", project["qpu_seconds"]),
            "name": payload.get("name", project["name"]),
            "description": payload.get("description", project["description"]),
            "user_ids": user_ids,
            "admin_id": admin_id,
            "admin_email": payload.get("admin_email", project["admin_email"]),
            "user_emails": [user_id_email_map[v] for v in user_ids],
            "is_personal": False,
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
                "qpu_seconds": item["qpu_seconds"],
                "is_active": item.get("is_active", True),
                "user_ids": [str(v) for v in item["user_ids"]],
                "admin_id": str(item["admin_id"]),
                "admin_email": USER_ID_EMAIL_MAP[str(item["admin_id"])],
                "user_emails": [USER_ID_EMAIL_MAP[str(v)] for v in item["user_ids"]],
                "name": item["name"],
                "description": item["description"],
                "is_personal": item.get("is_personal", False),
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
            }
            for item in [TEST_PROJECT_DICT, TEST_NO_QPU_PROJECT_DICT] + PROJECT_LIST
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": project_list}


@pytest.mark.parametrize("params, is_match", _PROJECT_QUERIES)
def test_admin_filter_projects(
    params, is_match, client, inserted_project_ids, admin_jwt_cookie
):
    """Admins can filter the projects at /admin/projects/"""
    expected = sorted(str(v["_id"]) for v in _ALL_PROJECTS if is_match(v))

    with client as client:
        response = client.get(
            "/admin/projects/", params=params, cookies=admin_jwt_cookie
        )
        got = sorted(v["id"] for v in response.json()["data"])

        assert response.status_code == 200
        assert 0 < len(expected) < len(_ALL_PROJECTS)
        assert got == expected


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
            "qpu_seconds": project["qpu_seconds"],
            "is_active": project["is_active"],
            "user_ids": project.get(
                "user_ids",
            ),
            "admin_id": project.get(
                "admin_id",
            ),
            "admin_email": USER_ID_EMAIL_MAP.get(
                project.get(
                    "admin_id",
                )
            ),
            "user_emails": [
                USER_ID_EMAIL_MAP.get(v) for v in project.get("user_ids", [])
            ],
            "name": project.get(
                "name",
            ),
            "description": project.get(
                "description",
            ),
            "is_personal": project.get("is_personal", False),
            "created_at": project.get(
                "created_at",
            ),
            "updated_at": project.get(
                "updated_at",
            ),
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


def test_admin_create_project_with_existing_name(client, admin_jwt_cookie, db):
    """POST /admin/projects/ refuses a second project of the same name"""
    with client as client:
        response = client.post(
            "/admin/projects/",
            json={**_NOTIFIED_PROJECT, "name": TEST_PROJECT_NAME},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "PROJECT_ALREADY_EXISTS"}
        assert db["auth_projects"].count_documents({"name": TEST_PROJECT_NAME}) == 1


def test_project_creation_notifies_the_new_members(client, admin_jwt_cookie, db):
    """Everyone put on a brand new project is told they were added"""
    with client as client:
        response = client.post(
            "/admin/projects/", json=_NOTIFIED_PROJECT, cookies=admin_jwt_cookie
        )
        member_notices = get_user_notices(db, TEST_OUTSIDER_ID)

        assert response.status_code == 201
        assert [item["type"] for item in member_notices] == [
            NoticeType.PROJECT_MEMBERSHIP_GRANTED.id
        ]
        assert member_notices[0]["body"] == (
            "jane.doe added you to notified project "
            f"({response.json()['id']}). You can now create API tokens for it."
        )


def test_project_creation_notifies_the_admin(client, admin_jwt_cookie, db):
    """The user named as admin hears about that, not only about membership"""
    with client as client:
        client.post(
            "/admin/projects/", json=_NOTIFIED_PROJECT, cookies=admin_jwt_cookie
        )
        admin_notice_types = {
            item["type"] for item in get_user_notices(db, TEST_USER_ID)
        }

        assert admin_notice_types == {
            NoticeType.PROJECT_MEMBERSHIP_GRANTED.id,
            NoticeType.PROJECT_ADMIN_ASSIGNED.id,
        }


def test_project_update_notifies_the_added_and_the_removed(
    client, admin_jwt_cookie, db
):
    """Replacing the member list is a grant for some and a revocation for others"""
    with client as client:
        response = client.put(
            f"/admin/projects/{TEST_PROJECT_ID}",
            json={"user_emails": [TEST_OUTSIDER_EMAIL]},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert [item["type"] for item in get_user_notices(db, TEST_OUTSIDER_ID)] == [
            NoticeType.PROJECT_MEMBERSHIP_GRANTED.id
        ]
        assert [item["type"] for item in get_user_notices(db, TEST_SYSTEM_USER_ID)] == [
            NoticeType.PROJECT_MEMBERSHIP_REVOKED.id
        ]
        assert get_user_notices(db, TEST_USER_ID) == []


def test_project_update_notifies_the_new_admin(client, admin_jwt_cookie, db):
    """Handing a project to someone else tells them they now run it"""
    with client as client:
        response = client.put(
            f"/admin/projects/{TEST_PROJECT_ID}",
            json={"admin_email": TEST_SYSTEM_USER_EMAIL},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert [item["type"] for item in get_user_notices(db, TEST_SYSTEM_USER_ID)] == [
            NoticeType.PROJECT_ADMIN_ASSIGNED.id
        ]


def test_project_update_that_changes_no_membership_notifies_nobody(
    client, admin_jwt_cookie, db
):
    """A rename must not spam every member"""
    with client as client:
        response = client.put(
            f"/admin/projects/{TEST_PROJECT_ID}",
            json={"name": "a new name"},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert db["notices"].count_documents({}) == 0


def test_admin_delete_personal_project(client, admin_jwt_cookie, db, personal_project):
    """An operator must be able to offboard a user without touching the database"""
    project_id = str(personal_project["_id"])

    with client as client:
        response = client.delete(
            f"/admin/projects/{project_id}", cookies=admin_jwt_cookie
        )

        assert response.status_code == 204
        assert get_db_record(db, Project, project_id) is None
        assert get_db_record(db, DeletedProject, project_id) is not None
