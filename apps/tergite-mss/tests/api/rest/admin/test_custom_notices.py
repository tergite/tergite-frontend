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
"""Integration tests for the /admin/notices routes"""
from beanie import PydanticObjectId

from tests._utils.auth import (
    TEST_OUTSIDER_EMAIL,
    TEST_SUPERUSER_ID,
    TEST_USER_EMAIL,
    TEST_USER_ID,
)
from tests._utils.mongodb import find_in_collection

_NOTICES_COLLECTION = "notices"
_ADMIN_NOTICE_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"
_USER_NOTICE_ID = "bbbbbbbbbbbbbbbbbbbbbbbb"
_BROADCAST_NOTICE_ID = "cccccccccccccccccccccccc"
_READ_USER_NOTICE_ID = "dddddddddddddddddddddddd"
_SYSTEM_NOTICE_ID = "ffffffffffffffffffffffff"
_NOTICE_PAYLOAD = {
    "message": "Important maintenance window",
    "severity": "warning",
    "starts_at": "2026-01-01T00:00:00Z",
    "expires_at": "2027-01-01T00:00:00Z",
}


def test_admin_publish_broadcast_notice(admin_jwt_cookie, client, db):
    """POST /admin/notices/ without target emails publishes one notice for everyone"""
    with client as client:
        response = client.post(
            "/admin/notices/", cookies=admin_jwt_cookie, json=_NOTICE_PAYLOAD
        )
        got = response.json()
        notices_in_db = find_in_collection(db, _NOTICES_COLLECTION)

        assert response.status_code == 200
        assert len(got) == 1
        assert got[0]["type"] == "custom-broadcast"
        assert got[0]["title"] == _NOTICE_PAYLOAD["message"]
        assert got[0]["body"] == _NOTICE_PAYLOAD["message"]
        assert got[0]["severity"] == _NOTICE_PAYLOAD["severity"]
        assert got[0]["starts_at"] == "2026-01-01T00:00:00.000Z"
        assert got[0]["expires_at"] == "2027-01-01T00:00:00.000Z"
        assert got[0]["created_by"] == TEST_SUPERUSER_ID
        assert got[0]["user_id"] is None
        assert got[0]["dismissed_by"] == []
        assert [str(item["_id"]) for item in notices_in_db] == [got[0]["id"]]


def test_admin_publish_notice_with_target_emails(admin_jwt_cookie, client, db):
    """POST /admin/notices/ with target emails publishes one notice per known user"""
    payload = {
        **_NOTICE_PAYLOAD,
        "target_user_emails": [TEST_USER_EMAIL, TEST_OUTSIDER_EMAIL, "no@such.user"],
    }

    with client as client:
        response = client.post(
            "/admin/notices/", cookies=admin_jwt_cookie, json=payload
        )
        got = response.json()
        notices_in_db = find_in_collection(db, _NOTICES_COLLECTION)

        assert response.status_code == 200
        assert {item["type"] for item in got} == {"custom"}
        assert {item["user_id"] for item in got} == {
            TEST_USER_ID,
            str(_get_user_id(db, TEST_OUTSIDER_EMAIL)),
        }
        assert {str(item["_id"]) for item in notices_in_db} == {
            item["id"] for item in got
        }


def test_non_admin_publish_notice(user_jwt_cookie, client, db):
    """POST /admin/notices/ by a non-admin is forbidden"""
    with client as client:
        response = client.post(
            "/admin/notices/", cookies=user_jwt_cookie, json=_NOTICE_PAYLOAD
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}
        assert find_in_collection(db, _NOTICES_COLLECTION) == []


def test_unauthenticated_publish_notice(client, db):
    """POST /admin/notices/ requires a signed-in user"""
    with client as client:
        response = client.post("/admin/notices/", json=_NOTICE_PAYLOAD)

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
        assert find_in_collection(db, _NOTICES_COLLECTION) == []


def test_admin_delete_notice(admin_jwt_cookie, client, db, inserted_notices):
    """DELETE /admin/notices/{notice_id} deletes the notice and returns it"""
    with client as client:
        response = client.delete(
            f"/admin/notices/{_ADMIN_NOTICE_ID}", cookies=admin_jwt_cookie
        )
        got = response.json()
        ids_in_db = [str(item["_id"]) for item in find_in_collection(db, "notices")]

        assert response.status_code == 200
        assert got["id"] == _ADMIN_NOTICE_ID
        assert got["title"] == "Notice for admin only"
        assert _ADMIN_NOTICE_ID not in ids_in_db
        assert len(ids_in_db) == len(inserted_notices) - 1


def test_non_admin_delete_notice(user_jwt_cookie, client, db, inserted_notices):
    """DELETE /admin/notices/{notice_id} by a non-admin is forbidden"""
    with client as client:
        response = client.delete(
            f"/admin/notices/{_USER_NOTICE_ID}", cookies=user_jwt_cookie
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}
        assert len(find_in_collection(db, _NOTICES_COLLECTION)) == len(inserted_notices)


def test_delete_non_existent_notice(admin_jwt_cookie, client):
    """DELETE /admin/notices/{notice_id} returns 404 when the notice does not exist"""
    with client as client:
        response = client.delete(
            f"/admin/notices/{_ADMIN_NOTICE_ID}", cookies=admin_jwt_cookie
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": f"notice of ID '{_ADMIN_NOTICE_ID}' not found"
        }


def test_admin_get_all_notices(admin_jwt_cookie, client, inserted_notices):
    """GET /admin/notices without a user_id returns every notice"""
    with client as client:
        response = client.get("/admin/notices", cookies=admin_jwt_cookie)
        got = response.json()

        assert response.status_code == 200
        assert got["skip"] == 0
        assert got["limit"] is None
        assert {item["id"] for item in got["data"]} == {
            str(item["_id"]) for item in inserted_notices
        }


def test_admin_get_notices_of_user(admin_jwt_cookie, client, inserted_notices):
    """GET /admin/notices?user_id=...&include_dismissed=true returns the user's own and broadcast notices"""
    expected_ids = {
        str(item["_id"])
        for item in inserted_notices
        if item["user_id"] in (PydanticObjectId(TEST_USER_ID), None)
    }

    with client as client:
        response = client.get(
            f"/admin/notices?user_id={TEST_USER_ID}&include_dismissed=true",
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert {item["id"] for item in response.json()["data"]} == expected_ids


def test_admin_get_notices_excludes_dismissed_by_default(
    admin_jwt_cookie, client, inserted_notices
):
    """GET /admin/notices?user_id=... leaves out the notices the user dismissed"""
    with client as client:
        response = client.get(
            f"/admin/notices?user_id={TEST_USER_ID}", cookies=admin_jwt_cookie
        )
        returned_ids = {item["id"] for item in response.json()["data"]}

        assert response.status_code == 200
        assert _USER_NOTICE_ID in returned_ids
        assert _READ_USER_NOTICE_ID not in returned_ids
        assert _ADMIN_NOTICE_ID not in returned_ids


def test_admin_get_notices_by_type(admin_jwt_cookie, client, inserted_notices):
    """GET /admin/notices?type=... returns only the notices of the given types"""
    with client as client:
        response = client.get(
            "/admin/notices?type=custom-broadcast&type=project-access-requested",
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert {item["id"] for item in response.json()["data"]} == {
            _BROADCAST_NOTICE_ID,
            _SYSTEM_NOTICE_ID,
        }


def test_non_admin_get_notices(user_jwt_cookie, client, inserted_notices):
    """GET /admin/notices by a non-admin is forbidden"""
    with client as client:
        response = client.get("/admin/notices", cookies=user_jwt_cookie)

        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}


def test_unauthenticated_get_notices(client, inserted_notices):
    """GET /admin/notices requires a signed-in user"""
    with client as client:
        response = client.get("/admin/notices")

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


def _get_user_id(db, email: str) -> PydanticObjectId:
    """Gets the id of the user of the given email

    Args:
        db: the mongo database where the users are stored
        email: the email of the user

    Returns:
        the id of the user
    """
    return db["auth_users"].find_one({"email": email})["_id"]
