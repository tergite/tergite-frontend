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

"""Tests for personal projects: auto-creation on login and permanence"""
import pytest

import settings
from services.auth import Project
from services.auth.projects.dtos import (
    personal_project_ext_id,
    personal_project_name,
)
from tests._utils.auth import TEST_GITHUB_PROFILE, get_db_record
from tests.conftest import get_auth_cookie

_GITHUB_CALLBACK = "/auth/github/callback"

# FIXME: Cleanup this file


@pytest.fixture
def personal_qpu_seconds():
    """Grants a non-zero personal allowance for the duration of the test"""
    original = settings.CONFIG.projects.personal_qpu_seconds
    settings.CONFIG.projects.personal_qpu_seconds = 5400
    yield 5400
    settings.CONFIG.projects.personal_qpu_seconds = original


@pytest.fixture
def personal_projects_disabled():
    """Turns off personal projects for the duration of the test"""
    original = settings.CONFIG.projects.personal_projects_enabled
    settings.CONFIG.projects.personal_projects_enabled = False
    yield
    settings.CONFIG.projects.personal_projects_enabled = original


def _login(client, cookie_oauth_state):
    return client.get(
        f"{_GITHUB_CALLBACK}?code=test&state={cookie_oauth_state}",
        follow_redirects=False,
    )


def _personal_project(db, user_id):
    return get_db_record(
        db, Project, _filter={"ext_id": personal_project_ext_id(user_id)}
    )


def test_login_creates_personal_project(
    client, github_user, cookie_oauth_state, db, personal_qpu_seconds
):
    """A user gets their personal project on first login"""
    with client as client:
        assert _login(client, cookie_oauth_state).status_code == 307

        user = db["auth_users"].find_one({"email": TEST_GITHUB_PROFILE["email"]})
        project = _personal_project(db, user["_id"])

        assert project is not None
        assert project["name"] == personal_project_name(TEST_GITHUB_PROFILE["email"])
        assert project["is_personal"] is True
        assert project["qpu_seconds"] == personal_qpu_seconds
        assert project["admin_id"] == str(user["_id"])
        assert project["user_ids"] == [str(user["_id"])]
        assert project["user_emails"] == [TEST_GITHUB_PROFILE["email"]]


def test_personal_project_defaults_to_zero_seconds(
    client, github_user, cookie_oauth_state, db
):
    """The unconfigured default grants nothing, so behaviour is unchanged on upgrade"""
    with client as client:
        _login(client, cookie_oauth_state)

        user = db["auth_users"].find_one({"email": TEST_GITHUB_PROFILE["email"]})

        assert _personal_project(db, user["_id"])["qpu_seconds"] == 0


def test_second_login_does_not_duplicate(client, github_user, cookie_oauth_state, db):
    """ensure_personal_project is idempotent across logins"""
    with client as client:
        _login(client, cookie_oauth_state)
        _login(client, cookie_oauth_state)

        user = db["auth_users"].find_one({"email": TEST_GITHUB_PROFILE["email"]})
        matches = db["auth_projects"].count_documents(
            {"admin_id": str(user["_id"]), "is_personal": True}
        )

        assert matches == 1


def test_existing_user_converges_on_login(
    client, chalmers_user, cookie_oauth_state, db, insert_chalmers_user
):
    """A user predating the feature gets their project on next login, with no migration"""
    with client as client:
        assert _personal_project(db, insert_chalmers_user["_id"]) is None

        response = client.get(
            f"/auth/chalmers/callback?code=test&state={cookie_oauth_state}",
            follow_redirects=False,
        )

        assert response.status_code == 307
        assert _personal_project(db, insert_chalmers_user["_id"]) is not None


def test_disabled_personal_projects(
    client, github_user, cookie_oauth_state, db, personal_projects_disabled
):
    """No personal project is created when the feature is switched off"""
    with client as client:
        assert _login(client, cookie_oauth_state).status_code == 307

        assert db["auth_projects"].count_documents({"is_personal": True}) == 0


def test_concurrent_creation_yields_one_project(
    client, github_user, cookie_oauth_state, db, mocker
):
    """A login losing the create race re-reads the winner rather than erroring

    Simulated by making the existence check miss once, so the insert hits the unique
    index on ext_id exactly as the loser of a real race would.
    """
    from services.auth.projects import ProjectDatabase

    real_get = ProjectDatabase.get_by_ext_id
    calls = {"n": 0}

    async def miss_once(ext_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real_get(ext_id)

    with client as client:
        _login(client, cookie_oauth_state)
        user = db["auth_users"].find_one({"email": TEST_GITHUB_PROFILE["email"]})
        mocker.patch.object(ProjectDatabase, "get_by_ext_id", side_effect=miss_once)

        assert _login(client, cookie_oauth_state).status_code == 307

        assert (
            db["auth_projects"].count_documents(
                {"admin_id": str(user["_id"]), "is_personal": True}
            )
            == 1
        )


def test_superuser_can_delete_a_personal_project(
    client, admin_jwt_cookie, db, github_user, cookie_oauth_state
):
    """An operator must be able to offboard a user without touching the database"""
    with client as client:
        _login(client, cookie_oauth_state)
        user = db["auth_users"].find_one({"email": TEST_GITHUB_PROFILE["email"]})
        project = _personal_project(db, user["_id"])

        response = client.delete(
            f"/admin/projects/{project['_id']}", cookies=admin_jwt_cookie
        )

        assert response.status_code == 204
        assert _personal_project(db, user["_id"]) is None


def test_owner_cannot_delete_their_own_personal_project(
    client, db, github_user, cookie_oauth_state
):
    """Self-deletion would hand out a fresh allowance on the next login"""
    with client as client:
        _login(client, cookie_oauth_state)
        user = db["auth_users"].find_one({"email": TEST_GITHUB_PROFILE["email"]})
        project = _personal_project(db, user["_id"])

        response = client.delete(
            f"/me/projects/{project['_id']}",
            cookies=get_auth_cookie(str(user["_id"])),
        )

        assert response.status_code == 403
        assert response.json() == {
            "detail": "you cannot delete your own personal project"
        }
        assert _personal_project(db, user["_id"]) is not None


def test_shared_project_can_still_be_deleted(client, admin_jwt_cookie, db, project_id):
    """The guard is limited to personal projects"""
    with client as client:
        response = client.delete(
            f"/admin/projects/{project_id}", cookies=admin_jwt_cookie
        )

        assert response.status_code == 204
        assert get_db_record(db, Project, str(project_id)) is None
