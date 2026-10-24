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

from libs.storage import generate_id
from services.auth import AppToken, DeletedProject, Project
from services.notices import Notice, NoticeType
from tests._utils.auth import (
    TEST_NO_QPU_PROJECT_DICT,
    TEST_OUTSIDER_ID,
    TEST_PROJECT_DICT,
    TEST_PROJECT_ID,
    TEST_PROJECT_NAME,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_ID,
    TEST_USER_ID,
    get_auth_cookie,
)
from tests._utils.date_time import get_current_timestamp_str
from tests._utils.notices import get_user_notices
from tests._utils.projects import PROJECT_QUERIES
from tests.conftest import PROJECT_LIST

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
_ALL_PROJECTS = [TEST_PROJECT_DICT, TEST_NO_QPU_PROJECT_DICT] + PROJECT_LIST
_SYSTEM_USER_MEMBERSHIP_URL = (
    f"/me/projects/{TEST_PROJECT_ID}/members/{TEST_SYSTEM_USER_ID}"
)


@pytest.mark.parametrize("params, is_match", PROJECT_QUERIES)
def test_filter_own_projects(
    params, is_match, client, inserted_project_ids, user_jwt_cookie
):
    """Any user can filter their own projects at /me/projects/"""
    expected = sorted(
        str(v["_id"])
        for v in _ALL_PROJECTS
        if TEST_USER_ID in [str(u) for u in v["user_ids"]] and is_match(v)
    )

    with client as client:
        response = client.get("/me/projects/", params=params, cookies=user_jwt_cookie)
        got = sorted(v["id"] for v in response.json()["data"])

        assert response.status_code == 200
        assert got == expected


def test_filter_projects_by_others_members(
    client, inserted_project_ids, user_jwt_cookie
):
    """Filtering by members finds only the user's own projects that they are in"""
    with client as client:
        response = client.get(
            "/me/projects/",
            params={"user_ids": TEST_SUPERUSER_ID},
            cookies=user_jwt_cookie,
        )
        got = sorted(v["id"] for v in response.json()["data"])

        assert response.status_code == 200
        assert got == sorted(
            project["_id"]
            for project in PROJECT_LIST
            if TEST_SUPERUSER_ID in project["user_ids"]
            and TEST_USER_ID in project["user_ids"]
        )


def test_filter_by_too_many_ids(client, user_jwt_cookie):
    """Filtering by more ids than a MongoDB $in handles well answers 400"""
    ids = [str(generate_id()) for _ in range(100)]

    with client as client:
        response = client.get(
            "/me/projects/", params={"id": ids}, cookies=user_jwt_cookie
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "too many items passed to query id; expected 99, got 100"
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
                "name": item.get("name"),
                "qpu_seconds": item["qpu_seconds"],
                "description": item.get("description"),
                "user_ids": [str(v) for v in item["user_ids"]],
                "admin_id": str(item["admin_id"]),
                "is_active": item.get("is_active", True),
                "is_personal": item.get("is_personal", False),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }
            for item in [TEST_PROJECT_DICT, TEST_NO_QPU_PROJECT_DICT] + PROJECT_LIST
            if user_id in [str(v) for v in item["user_ids"]]
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": project_list}


@pytest.mark.parametrize(
    "user_id, cookies, project",
    [
        *_MY_ADMINISTERED_PROJECT_REQUESTS[:1],
        *_MY_NON_ADMINISTERED_PROJECT_REQUESTS[:1],
    ],
)
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


@pytest.mark.parametrize("user_id, cookies, project", _OTHERS_PROJECT_REQUESTS[:1])
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


@pytest.mark.parametrize(
    "user_id, cookies, project", _MY_ADMINISTERED_PROJECT_REQUESTS[:2]
)
def test_delete_own_project(
    user_id, cookies, project, client, inserted_projects, db, freezer
):
    """Any user can delete the project they administer at /me/projects/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = project["_id"]
        url = f"/me/projects/{_id}"

        now = get_current_timestamp_str()
        original = db.get(Project, _id)
        assert original is not None
        response = client.delete(url, cookies=cookies)

        deleted_project = db.get(DeletedProject, _id)
        timestamps = {"created_at", "updated_at"}

        assert response.status_code == 204
        assert db.get(Project, _id) is None
        assert deleted_project.model_dump(exclude=timestamps) == original.model_dump(
            exclude=timestamps
        )
        assert deleted_project.created_at == deleted_project.updated_at == now


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

        assert db.get(Project, project_id) is not None
        response = client.delete(url, cookies=cookies)

        got = response.json()
        expected = {"detail": "Forbidden"}

        assert response.status_code == 403
        assert got == expected
        assert db.get(Project, project_id) is not None


def test_owner_cannot_delete_their_own_personal_project(
    client, user_jwt_cookie, db, personal_project
):
    """Deleting one's own personal project would hand out a fresh allowance on the next login"""
    project_id = personal_project["_id"]

    with client as client:
        response = client.delete(f"/me/projects/{project_id}", cookies=user_jwt_cookie)

        assert response.status_code == 403
        assert response.json() == {
            "detail": "you cannot delete your own personal project"
        }
        assert db.get(Project, project_id) is not None


def test_project_admin_removes_a_member(client, user_jwt_cookie, db):
    """DELETE /me/projects/{id}/members/{member_id} by the project admin removes the member"""
    with client as client:
        response = client.delete(_SYSTEM_USER_MEMBERSHIP_URL, cookies=user_jwt_cookie)
        project = db.get(Project, TEST_PROJECT_ID)

        assert response.status_code == 204
        assert project.user_ids == [TEST_USER_ID]


def test_removing_a_member_revokes_their_tokens(client, user_jwt_cookie, db):
    """The removed member's app tokens for the project stop existing"""
    token_filter = {"user_id": TEST_SYSTEM_USER_ID, "project_id": TEST_PROJECT_ID}

    with client as client:
        tokens_before = db.count(AppToken, token_filter)
        client.delete(_SYSTEM_USER_MEMBERSHIP_URL, cookies=user_jwt_cookie)
        tokens_after = db.count(AppToken, token_filter)

        assert tokens_before == 1
        assert tokens_after == 0


def test_removing_a_member_notifies_them(client, user_jwt_cookie, db):
    """The removed member is told, rather than silently losing access"""
    with client as client:
        client.delete(_SYSTEM_USER_MEMBERSHIP_URL, cookies=user_jwt_cookie)
        member_notices = get_user_notices(db, TEST_SYSTEM_USER_ID)

        assert [item.type for item in member_notices] == [
            NoticeType.PROJECT_MEMBERSHIP_REVOKED.id
        ]
        assert member_notices[0].title == f"You were removed from {TEST_PROJECT_NAME}"


def test_superuser_removes_a_member(client, admin_jwt_cookie, db):
    """A superuser may remove a member from any project, not only ones they administer"""
    with client as client:
        response = client.delete(_SYSTEM_USER_MEMBERSHIP_URL, cookies=admin_jwt_cookie)
        project = db.get(Project, TEST_PROJECT_ID)

        assert response.status_code == 204
        assert TEST_SYSTEM_USER_ID not in project.user_ids


def test_non_admin_cannot_remove_a_member(client, system_user_jwt_cookie, db):
    """Someone who neither administers the project nor is a superuser is forbidden"""
    url = f"/me/projects/{TEST_PROJECT_ID}/members/{TEST_USER_ID}"

    with client as client:
        response = client.delete(url, cookies=system_user_jwt_cookie)
        project = db.get(Project, TEST_PROJECT_ID)

        assert response.status_code == 403
        assert TEST_USER_ID in project.user_ids


def test_cannot_remove_the_project_admin(client, admin_jwt_cookie, db):
    """Removing the admin would orphan the project, so it is refused"""
    url = f"/me/projects/{TEST_PROJECT_ID}/members/{TEST_USER_ID}"

    with client as client:
        response = client.delete(url, cookies=admin_jwt_cookie)
        project = db.get(Project, TEST_PROJECT_ID)

        assert response.status_code == 400
        assert response.json() == {"detail": "the project admin cannot be removed"}
        assert TEST_USER_ID in project.user_ids


def test_remove_a_non_member(client, user_jwt_cookie, db):
    """Removing someone who is not on the project answers 404 and notifies nobody"""
    url = f"/me/projects/{TEST_PROJECT_ID}/members/{TEST_OUTSIDER_ID}"

    with client as client:
        response = client.delete(url, cookies=user_jwt_cookie)

        assert response.status_code == 404
        assert response.json() == {"detail": "user not a member"}
        assert db.count(Notice) == 0


def test_remove_a_member_twice(client, user_jwt_cookie, db):
    """A repeated removal finds no member and does not notify again"""
    with client as client:
        client.delete(_SYSTEM_USER_MEMBERSHIP_URL, cookies=user_jwt_cookie)
        response = client.delete(_SYSTEM_USER_MEMBERSHIP_URL, cookies=user_jwt_cookie)

        assert response.status_code == 404
        assert db.count(Notice) == 1


def test_remove_a_member_from_unknown_project(client, user_jwt_cookie):
    """Removing a member from a project that does not exist answers 404"""
    url = f"/me/projects/{generate_id()}/members/{TEST_SYSTEM_USER_ID}"

    with client as client:
        response = client.delete(url, cookies=user_jwt_cookie)

        assert response.status_code == 404


def test_unauthenticated_remove_a_member(client, db):
    """Removing a member requires a signed-in user"""
    with client as client:
        response = client.delete(_SYSTEM_USER_MEMBERSHIP_URL)
        project = db.get(Project, TEST_PROJECT_ID)

        assert response.status_code == 401
        assert TEST_SYSTEM_USER_ID in project.user_ids
