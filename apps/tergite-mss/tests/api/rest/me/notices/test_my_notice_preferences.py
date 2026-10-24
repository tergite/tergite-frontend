# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Integration tests for the /me/notices/preferences routes"""

from services.notices import NoticePreferences, NoticeType
from tests._utils.auth import TEST_USER_ID

_DEFAULT_PREFS = {item.id: True for item in NoticeType}


def test_view_default_email_preferences(client, user_jwt_cookie):
    """GET /me/notices/preferences/ defaults every notice type to being emailed"""
    with client as client:
        response = client.get("/me/notices/preferences/", cookies=user_jwt_cookie)

        assert response.status_code == 200
        assert response.json() == _DEFAULT_PREFS


def test_update_email_preferences(client, user_jwt_cookie, db):
    """PUT /me/notices/preferences/ changes only the named types and persists them"""
    with client as client:
        response = client.put(
            "/me/notices/preferences/",
            cookies=user_jwt_cookie,
            json={"qpu-seconds-granted": False},
        )
        record = db.find_one(NoticePreferences, {"user_id": TEST_USER_ID})

        assert response.status_code == 200
        assert response.json() == {**_DEFAULT_PREFS, "qpu-seconds-granted": False}
        assert record.email_prefs == {"qpu-seconds-granted": False}


def test_update_email_preferences_keeps_earlier_updates(client, user_jwt_cookie, db):
    """A later partial update leaves the types set by an earlier one untouched"""
    with client as client:
        client.put(
            "/me/notices/preferences/",
            cookies=user_jwt_cookie,
            json={"qpu-seconds-granted": False},
        )
        client.put(
            "/me/notices/preferences/",
            cookies=user_jwt_cookie,
            json={"custom": False, "qpu-seconds-granted": True},
        )
        response = client.get("/me/notices/preferences/", cookies=user_jwt_cookie)

        assert response.json() == {**_DEFAULT_PREFS, "custom": False}
        assert db.count(NoticePreferences) == 1


def test_update_unknown_notice_type_preference(client, user_jwt_cookie, db):
    """PUT /me/notices/preferences/ rejects a notice type that does not exist"""
    with client as client:
        response = client.put(
            "/me/notices/preferences/",
            cookies=user_jwt_cookie,
            json={"no-such-type": False},
        )

        assert response.status_code == 422
        assert db.count(NoticePreferences) == 0


def test_unauthenticated_view_email_preferences(client):
    """GET /me/notices/preferences/ requires a signed-in user"""
    with client as client:
        response = client.get("/me/notices/preferences/")

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


def test_unauthenticated_update_email_preferences(client, db):
    """PUT /me/notices/preferences/ requires a signed-in user"""
    with client as client:
        response = client.put("/me/notices/preferences/", json={"custom": False})

        assert response.status_code == 401
        assert db.count(NoticePreferences) == 0
