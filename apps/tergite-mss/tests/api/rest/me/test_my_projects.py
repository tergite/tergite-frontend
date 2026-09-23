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

import pytest
from pytest_lazyfixture import lazy_fixture

from services.auth import DeletedProject, Project
from tests._utils.auth import (
    TEST_NO_QPU_PROJECT_DICT,
    TEST_PROJECT_DICT,
    TEST_SUPERUSER_ID,
    TEST_USER_ID,
    get_db_record,
)
from tests._utils.date_time import get_current_timestamp_str
from tests._utils.records import prune
from tests.conftest import PROJECT_LIST, get_auth_cookie

_MY_PROJECT_REQUESTS = [
    (user_id, get_auth_cookie(user_id), project)
    for project in PROJECT_LIST
    for user_id in project["user_ids"]
]
_MY_ADMINISTERED_PROJECT_REQUESTS = [
    (project["admin_id"], get_auth_cookie(project["admin_id"]), project)
    for project in PROJECT_LIST
]
_MY_NON_ADMINISTERED_PROJECT_REQUESTS = [
    (user_id, get_auth_cookie(user_id), project)
    for project in PROJECT_LIST
    for user_id in project["user_ids"]
    if user_id != project["admin_id"]
]
_OTHERS_PROJECT_REQUESTS = [
    (user_id, get_auth_cookie(user_id), project)
    for project in PROJECT_LIST
    for user_id in [TEST_USER_ID, TEST_SUPERUSER_ID]
    if user_id not in project["user_ids"]
]
_USER_ID_COOKIES_FIXTURE = [
    (TEST_USER_ID, lazy_fixture("user_jwt_cookie")),
    (TEST_SUPERUSER_ID, lazy_fixture("admin_jwt_cookie")),
]
_EXTRA_PROJECT_DEFAULTS = {
    "resource_ids": [],
    "source": "internal",
    "user_emails": None,
    "admin_email": None,
    "is_personal": False,
    "low_qpu_notified_at": None,
}


@pytest.mark.parametrize("user_id, cookies", _USER_ID_COOKIES_FIXTURE)
def test_view_own_projects_in_less_detail(
    user_id, cookies, client, inserted_project_ids
):
    """Any user can view only their own projects at /me/projects/
    without user_ids"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/me/projects/", cookies=cookies)

        got = response.json()
        project_list = [
            {
                "id": str(item["_id"]),
                "name": item.get("name", None),
                "ext_id": item["ext_id"],
                "qpu_seconds": item["qpu_seconds"],
                "description": item.get("description", None),
                "user_ids": item.get("user_ids", None),
                "admin_id": item.get("admin_id", None),
                "is_active": item.get("is_active", True),
                "is_personal": item.get("is_personal", False),
                "created_at": item.get("created_at", None),
                "updated_at": item.get("updated_at", None),
            }
            for item in [TEST_PROJECT_DICT, TEST_NO_QPU_PROJECT_DICT] + PROJECT_LIST
            if user_id in item["user_ids"]
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": project_list}


@pytest.mark.parametrize("user_id, cookies, project", _MY_PROJECT_REQUESTS)
def test_view_my_project_in_less_detail(
    user_id, cookies, project, client, inserted_projects
):
    """Any user can view only their own single project at /me/projects/{id}
    without user_emails"""
    # using context manager to ensure on_startup runs
    with client as client:
        project_id = project["_id"]
        url = f"/me/projects/{project_id}"
        response = client.get(url, cookies=cookies)

        got = response.json()
        expected = {
            "id": project_id,
            "name": project["name"],
            "ext_id": project["ext_id"],
            "qpu_seconds": project["qpu_seconds"],
            "description": project["description"],
            "user_ids": project["user_ids"],
            "admin_id": project["admin_id"],
            "is_active": project.get("is_active", True),
            "is_personal": project.get("is_personal", False),
            "created_at": project["created_at"],
            "updated_at": project["updated_at"],
        }

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("user_id, cookies, project", _OTHERS_PROJECT_REQUESTS)
def test_view_others_project_is_not_allowed(
    user_id, cookies, project, client, inserted_projects
):
    """No user can view other's projects at /me/projects/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        project_id = project["_id"]
        url = f"/me/projects/{project_id}"
        response = client.get(url, cookies=cookies)

        got = response.json()
        expected = {"detail": "the project does not exist."}

        assert response.status_code == 404
        assert got == expected


@pytest.mark.parametrize("user_id, cookies, project", _MY_ADMINISTERED_PROJECT_REQUESTS)
def test_delete_own_project(
    user_id, cookies, project, client, inserted_projects, db, freezer
):
    """Any user can delete the project they administer at /me/projects/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = project["_id"]
        url = f"/me/projects/{_id}"

        now = get_current_timestamp_str()
        original = get_db_record(db, Project, _id)
        assert original is not None
        response = client.delete(url, cookies=cookies)

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


@pytest.mark.parametrize(
    "user_id, cookies, project", _MY_NON_ADMINISTERED_PROJECT_REQUESTS
)
def test_delete_others_project_is_not_allowed(
    user_id, cookies, project, client, inserted_projects, db
):
    """No user can delete projects they don't administer at /me/projects/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        project_id = project["_id"]
        url = f"/me/projects/{project_id}"

        assert get_db_record(db, Project, project_id) is not None
        response = client.delete(url, cookies=cookies)

        got = response.json()
        expected = {"detail": "Forbidden"}

        assert response.status_code == 403
        assert got == expected
        assert get_db_record(db, Project, project_id) is not None
