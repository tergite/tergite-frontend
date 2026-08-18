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

"""Tests for removing a member from a project"""
from beanie import PydanticObjectId

from services.auth import Project
from services.notifications import NotificationType
from tests._utils.auth import (
    TEST_OUTSIDER_EMAIL,
    TEST_OUTSIDER_ID,
    TEST_PROJECT_ID,
    TEST_SYSTEM_USER_EMAIL,
    TEST_SYSTEM_USER_ID,
    TEST_USER_ID,
    get_db_record,
)

_TOKEN_COLLECTION = "auth_app_tokens"


def _url(project_id=TEST_PROJECT_ID, member_id=TEST_SYSTEM_USER_ID):
    return f"/me/projects/{project_id}/members/{member_id}"


def test_project_admin_removes_a_member(client, user_jwt_cookie, db):
    """The project admin can remove someone from the project they administer"""
    with client as client:
        response = client.delete(_url(), cookies=user_jwt_cookie)

        assert response.status_code == 204
        project = get_db_record(db, Project, TEST_PROJECT_ID)
        assert TEST_SYSTEM_USER_ID not in project["user_ids"]


def test_removal_revokes_the_members_tokens(client, user_jwt_cookie, db):
    """Going through the project manager revokes the removed member's app tokens"""
    with client as client:
        before = db[_TOKEN_COLLECTION].count_documents(
            {
                "user_id": PydanticObjectId(TEST_SYSTEM_USER_ID),
                "project_ext_id": "test-project-1",
            }
        )
        assert before == 1

        client.delete(_url(), cookies=user_jwt_cookie)

        after = db[_TOKEN_COLLECTION].count_documents(
            {
                "user_id": PydanticObjectId(TEST_SYSTEM_USER_ID),
                "project_ext_id": "test-project-1",
            }
        )
        assert after == 0


def test_removal_notifies_the_removed_member(client, user_jwt_cookie, db):
    """The removed member is told, rather than silently losing access"""
    with client as client:
        client.delete(_url(), cookies=user_jwt_cookie)

        got = list(
            db["notifications"].find({"user_id": PydanticObjectId(TEST_SYSTEM_USER_ID)})
        )

        assert [item["type"] for item in got] == [
            NotificationType.PROJECT_MEMBERSHIP_REVOKED
        ]
        assert "test-project" in got[0]["title"]


def test_removal_also_drops_the_email(client, user_jwt_cookie, db):
    """user_emails is kept in step with user_ids"""
    db["auth_projects"].update_one(
        {"_id": PydanticObjectId(TEST_PROJECT_ID)},
        {"$set": {"user_emails": [TEST_SYSTEM_USER_EMAIL, TEST_OUTSIDER_EMAIL]}},
    )

    with client as client:
        response = client.delete(_url(), cookies=user_jwt_cookie)

        assert response.status_code == 204
        project = get_db_record(db, Project, TEST_PROJECT_ID)
        assert TEST_SYSTEM_USER_EMAIL not in project["user_emails"]
        assert TEST_OUTSIDER_EMAIL in project["user_emails"]


def test_superuser_removes_a_member(client, admin_jwt_cookie, db):
    """A superuser may remove from any project, not only ones they administer"""
    with client as client:
        response = client.delete(_url(), cookies=admin_jwt_cookie)

        assert response.status_code == 204
        project = get_db_record(db, Project, TEST_PROJECT_ID)
        assert TEST_SYSTEM_USER_ID not in project["user_ids"]


def test_non_admin_cannot_remove(client, outsider_jwt_cookie, db):
    """Someone who neither administers the project nor is a superuser gets 403"""
    with client as client:
        response = client.delete(_url(), cookies=outsider_jwt_cookie)

        assert response.status_code == 403
        project = get_db_record(db, Project, TEST_PROJECT_ID)
        assert TEST_SYSTEM_USER_ID in project["user_ids"]


def test_cannot_remove_the_project_admin(client, user_jwt_cookie, db):
    """Removing the admin would orphan the project, so it is refused"""
    with client as client:
        response = client.delete(_url(member_id=TEST_USER_ID), cookies=user_jwt_cookie)

        assert response.status_code == 400
        assert response.json() == {"detail": "the project admin cannot be removed"}
        project = get_db_record(db, Project, TEST_PROJECT_ID)
        assert TEST_USER_ID in project["user_ids"]


def test_removing_a_non_member_is_a_no_op(client, user_jwt_cookie, db):
    """Idempotent: nothing to do for someone who is not on the project"""
    with client as client:
        response = client.delete(
            _url(member_id=TEST_OUTSIDER_ID), cookies=user_jwt_cookie
        )

        assert response.status_code == 204
        assert db["notifications"].count_documents({}) == 0


def test_removal_twice_is_a_no_op(client, user_jwt_cookie, db):
    """A repeated removal neither errors nor notifies again"""
    with client as client:
        client.delete(_url(), cookies=user_jwt_cookie)
        response = client.delete(_url(), cookies=user_jwt_cookie)

        assert response.status_code == 204
        assert db["notifications"].count_documents({}) == 1


def test_remove_from_unknown_project(client, user_jwt_cookie):
    """A project that does not exist is a 404"""
    with client as client:
        response = client.delete(
            _url(project_id=str(PydanticObjectId())), cookies=user_jwt_cookie
        )

        assert response.status_code == 404


def test_unauthenticated_removal(client):
    """Removal needs a signed-in user"""
    with client as client:
        assert client.delete(_url()).status_code == 401
