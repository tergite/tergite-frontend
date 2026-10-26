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
"""Integration tests for the /me/notices routes"""

from services.notices import Notice
from tests._utils.auth import (
    TEST_USER_ID,
)

_ADMIN_NOTICE_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"
_USER_NOTICE_ID = "bbbbbbbbbbbbbbbbbbbbbbbb"
_BROADCAST_NOTICE_ID = "cccccccccccccccccccccccc"
_READ_USER_NOTICE_ID = "dddddddddddddddddddddddd"
_FUTURE_USER_NOTICE_ID = "eeeeeeeeeeeeeeeeeeeeeeee"
_SYSTEM_USER_NOTICE_ID = "ffffffffffffffffffffffff"


def test_view_my_notices(client, user_jwt_cookie, inserted_notices):
    """GET /me/notices/ returns the user's own and broadcast notices, newest first"""
    with client as client:
        response = client.get("/me/notices/", cookies=user_jwt_cookie)
        got = response.json()

        assert response.status_code == 200
        assert got["skip"] == 0
        assert got["limit"] is None
        assert [item["id"] for item in got["data"]] == [
            _SYSTEM_USER_NOTICE_ID,
            _FUTURE_USER_NOTICE_ID,
            _READ_USER_NOTICE_ID,
            _BROADCAST_NOTICE_ID,
            _USER_NOTICE_ID,
        ]


def test_view_my_notices_serializes_each_notice(
    client, user_jwt_cookie, inserted_notices
):
    """GET /me/notices/ returns each notice with JSON-friendly ids and its severity"""
    with client as client:
        response = client.get("/me/notices/?limit=1", cookies=user_jwt_cookie)
        got = response.json()["data"][0]

        assert got["id"] == _SYSTEM_USER_NOTICE_ID
        assert got["user_id"] == TEST_USER_ID
        assert got["type"] == "project-access-requested"
        assert got["title"] == "Access request for test-project"
        assert got["ref_type"] == "user_request"
        assert got["ref_id"] == "a1b2c3d4e5f6a7b8c9d0e1f2"
        assert got["severity"] == 3
        assert got["read_at"] is None
        assert got["dismissed_by"] == []


def test_paginate_my_notices(client, user_jwt_cookie, inserted_notices):
    """GET /me/notices/?skip=...&limit=... returns the requested page"""
    with client as client:
        response = client.get("/me/notices/?skip=1&limit=2", cookies=user_jwt_cookie)
        got = response.json()

        assert response.status_code == 200
        assert got["skip"] == 1
        assert got["limit"] == 2
        assert [item["id"] for item in got["data"]] == [
            _FUTURE_USER_NOTICE_ID,
            _READ_USER_NOTICE_ID,
        ]


def test_filter_my_notices_by_type(client, user_jwt_cookie, inserted_notices):
    """GET /me/notices/?type=... returns only the notices of the given types"""
    with client as client:
        custom = client.get("/me/notices/?type=custom", cookies=user_jwt_cookie)
        many_types = client.get(
            "/me/notices/?type=custom-broadcast&type=project-access-requested",
            cookies=user_jwt_cookie,
        )
        unmatched = client.get(
            "/me/notices/?type=qpu-seconds-granted", cookies=user_jwt_cookie
        )

        assert [item["id"] for item in custom.json()["data"]] == [
            _FUTURE_USER_NOTICE_ID,
            _READ_USER_NOTICE_ID,
            _USER_NOTICE_ID,
        ]
        assert [item["id"] for item in many_types.json()["data"]] == [
            _SYSTEM_USER_NOTICE_ID,
            _BROADCAST_NOTICE_ID,
        ]
        assert unmatched.json()["data"] == []


def test_filter_my_notices_by_read_status(client, user_jwt_cookie, inserted_notices):
    """GET /me/notices/?is_read=... separates the read notices from the unread"""
    with client as client:
        read = client.get("/me/notices/?is_read=true", cookies=user_jwt_cookie)
        unread = client.get("/me/notices/?is_read=false", cookies=user_jwt_cookie)

        assert [item["id"] for item in read.json()["data"]] == [_READ_USER_NOTICE_ID]
        assert [item["id"] for item in unread.json()["data"]] == [
            _SYSTEM_USER_NOTICE_ID,
            _FUTURE_USER_NOTICE_ID,
            _BROADCAST_NOTICE_ID,
            _USER_NOTICE_ID,
        ]


def test_unauthenticated_view_my_notices(client, inserted_notices):
    """GET /me/notices/ requires a signed-in user"""
    with client as client:
        response = client.get("/me/notices/")

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


def test_dismiss_my_notice(client, user_jwt_cookie, db, inserted_notices):
    """POST /me/notices/{id}/dismiss marks the user's notice read"""
    with client as client:
        response = client.post(
            f"/me/notices/{_USER_NOTICE_ID}/dismiss", cookies=user_jwt_cookie
        )
        notice = db.get(Notice, _USER_NOTICE_ID)

        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        assert notice.read_at is not None
        assert notice.dismissed_by == [TEST_USER_ID]


def test_dismiss_broadcast_notice(client, user_jwt_cookie, db, inserted_notices):
    """POST /me/notices/{id}/dismiss records the reader of a broadcast without a read_at"""
    with client as client:
        response = client.post(
            f"/me/notices/{_BROADCAST_NOTICE_ID}/dismiss", cookies=user_jwt_cookie
        )
        notice = db.get(Notice, _BROADCAST_NOTICE_ID)

        assert response.status_code == 200
        assert notice.read_at is None
        assert notice.dismissed_by == [TEST_USER_ID]


def test_dismiss_my_notice_twice(client, user_jwt_cookie, db, inserted_notices):
    """Dismissing a read notice again does not record the reader twice"""
    with client as client:
        response = client.post(
            f"/me/notices/{_READ_USER_NOTICE_ID}/dismiss", cookies=user_jwt_cookie
        )
        notice = db.get(Notice, _READ_USER_NOTICE_ID)

        assert response.status_code == 200
        assert notice.dismissed_by == [TEST_USER_ID]


def test_cannot_dismiss_another_users_notice(
    client, user_jwt_cookie, db, inserted_notices
):
    """POST /me/notices/{id}/dismiss answers 404 for a notice addressed to someone else"""
    with client as client:
        response = client.post(
            f"/me/notices/{_ADMIN_NOTICE_ID}/dismiss", cookies=user_jwt_cookie
        )
        notice = db.get(Notice, _ADMIN_NOTICE_ID)

        assert response.status_code == 404
        assert notice.read_at is None
        assert notice.dismissed_by == []


def test_dismiss_non_existent_notice(client, user_jwt_cookie):
    """POST /me/notices/{id}/dismiss answers 404 for a notice that does not exist"""
    with client as client:
        response = client.post(
            f"/me/notices/{_USER_NOTICE_ID}/dismiss", cookies=user_jwt_cookie
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": f"notice of ID '{_USER_NOTICE_ID}' not found"
        }


def test_unauthenticated_dismiss_notice(client, db, inserted_notices):
    """POST /me/notices/{id}/dismiss requires a signed-in user"""
    with client as client:
        response = client.post(f"/me/notices/{_USER_NOTICE_ID}/dismiss")

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
        assert db.get(Notice, _USER_NOTICE_ID).dismissed_by == []


def test_unread_my_notice(client, user_jwt_cookie, db, inserted_notices):
    """POST /me/notices/{id}/unread marks the user's read notice unread"""
    with client as client:
        response = client.post(
            f"/me/notices/{_READ_USER_NOTICE_ID}/unread", cookies=user_jwt_cookie
        )
        notice = db.get(Notice, _READ_USER_NOTICE_ID)

        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        assert notice.read_at is None
        assert notice.dismissed_by == []


def test_cannot_unread_another_users_notice(client, admin_jwt_cookie, inserted_notices):
    """POST /me/notices/{id}/unread answers 404 for a notice addressed to someone else"""
    with client as client:
        response = client.post(
            f"/me/notices/{_READ_USER_NOTICE_ID}/unread", cookies=admin_jwt_cookie
        )

        assert response.status_code == 404


def test_dismiss_all_my_notices(client, user_jwt_cookie, db, inserted_notices):
    """POST /me/notices/dismiss marks every unread notice of the user read"""
    with client as client:
        response = client.post("/me/notices/dismiss", cookies=user_jwt_cookie)
        unread = client.get("/me/notices/?is_read=false", cookies=user_jwt_cookie)

        assert response.status_code == 200
        assert response.json() == {"status": "success", "detail": "4 notices updated"}
        assert unread.json()["data"] == []
        assert db.get(Notice, _ADMIN_NOTICE_ID).dismissed_by == []


def test_unread_all_my_notices(client, user_jwt_cookie, inserted_notices):
    """POST /me/notices/unread marks every read notice of the user unread"""
    with client as client:
        response = client.post("/me/notices/unread", cookies=user_jwt_cookie)
        read = client.get("/me/notices/?is_read=true", cookies=user_jwt_cookie)

        assert response.status_code == 200
        assert response.json() == {"status": "success", "detail": "1 notices updated"}
        assert read.json()["data"] == []


def test_unauthenticated_dismiss_all_notices(client, db, inserted_notices):
    """POST /me/notices/dismiss requires a signed-in user"""
    with client as client:
        response = client.post("/me/notices/dismiss")

        assert response.status_code == 401
        assert len([notice for notice in db.find(Notice) if notice.dismissed_by]) == 1
