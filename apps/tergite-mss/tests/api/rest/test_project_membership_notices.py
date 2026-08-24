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

"""Tests that an admin editing a project tells the users whose standing changed"""
from beanie import PydanticObjectId

from services.notifications import NotificationType
from tests._utils.auth import (
    TEST_OUTSIDER_EMAIL,
    TEST_OUTSIDER_ID,
    TEST_PROJECT_ID,
    TEST_SYSTEM_USER_EMAIL,
    TEST_SYSTEM_USER_ID,
    TEST_USER_EMAIL,
    TEST_USER_ID,
)

_COLLECTION = "notifications"
_URL = "/admin/projects/"


def _types_for(db, user_id):
    return [
        item["type"]
        for item in db[_COLLECTION].find({"user_id": PydanticObjectId(user_id)})
    ]


def _create(client, cookie, **overrides):
    body = {
        "admin_email": TEST_USER_EMAIL,
        "user_emails": [TEST_OUTSIDER_EMAIL],
        "ext_id": "notified-project",
        "is_active": True,
        "name": "notified project",
        "description": "a project whose members hear about it",
        "qpu_seconds": 100,
        **overrides,
    }
    return client.post(_URL, json=body, cookies=cookie)


def test_creation_tells_the_new_members(client, admin_jwt_cookie, db):
    """Everyone put on a brand new project is told they were added"""
    with client as client:
        assert _create(client, admin_jwt_cookie).status_code == 201

        assert _types_for(db, TEST_OUTSIDER_ID) == [
            NotificationType.PROJECT_MEMBERSHIP_GRANTED
        ]


def test_creation_tells_the_admin_they_administer_it(client, admin_jwt_cookie, db):
    """The user named as admin hears about that, not only about membership"""
    with client as client:
        assert _create(client, admin_jwt_cookie).status_code == 201

        assert set(_types_for(db, TEST_USER_ID)) == {
            NotificationType.PROJECT_MEMBERSHIP_GRANTED,
            NotificationType.PROJECT_ADMIN_ASSIGNED,
        }


def test_update_tells_the_added_and_the_removed(client, admin_jwt_cookie, db):
    """Replacing the member list is a grant for some and a revocation for others"""
    with client as client:
        response = client.put(
            f"{_URL}{TEST_PROJECT_ID}",
            json={"user_emails": [TEST_OUTSIDER_EMAIL]},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert NotificationType.PROJECT_MEMBERSHIP_GRANTED in _types_for(
            db, TEST_OUTSIDER_ID
        )
        assert NotificationType.PROJECT_MEMBERSHIP_REVOKED in _types_for(
            db, TEST_SYSTEM_USER_ID
        )


def test_update_tells_the_new_admin(client, admin_jwt_cookie, db):
    """Handing a project to someone else tells them they now run it"""
    with client as client:
        response = client.put(
            f"{_URL}{TEST_PROJECT_ID}",
            json={"admin_email": TEST_SYSTEM_USER_EMAIL},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert NotificationType.PROJECT_ADMIN_ASSIGNED in _types_for(
            db, TEST_SYSTEM_USER_ID
        )


def test_update_that_changes_nothing_notifies_nobody(client, admin_jwt_cookie, db):
    """A rename must not spam every member"""
    with client as client:
        before = db[_COLLECTION].count_documents({})

        response = client.put(
            f"{_URL}{TEST_PROJECT_ID}",
            json={"name": "a new name"},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert db[_COLLECTION].count_documents({}) == before
