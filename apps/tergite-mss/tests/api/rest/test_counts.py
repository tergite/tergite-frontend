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
"""Integration tests for the /counts routes"""
from datetime import datetime, timedelta, timezone

from tests._utils.auth import TEST_SUPERUSER_ID, TEST_USER_ID


def test_admin_count_all_notices(admin_jwt_cookie, client, inserted_notices):
    """GET /counts/notices by an admin counts every notice when no user_id is given"""
    with client as client:
        response = client.get("/counts/notices", cookies=admin_jwt_cookie)

        assert response.status_code == 200
        assert response.json() == {"count": len(inserted_notices)}


def test_admin_count_empty_notices(admin_jwt_cookie, client):
    """GET /counts/notices returns count of 0 when no notices exist"""
    with client as client:
        response = client.get("/counts/notices", cookies=admin_jwt_cookie)

        assert response.status_code == 200
        assert response.json() == {"count": 0}


def test_admin_count_notices_of_user(admin_jwt_cookie, client, inserted_notices):
    """GET /counts/notices?user_id=...&include_dismissed=true counts the user's own and broadcast notices"""
    with client as client:
        response = client.get(
            f"/counts/notices?user_id={TEST_USER_ID}&include_dismissed=true",
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert response.json() == {"count": 5}


def test_admin_count_notices_excludes_dismissed_by_default(
    admin_jwt_cookie, client, inserted_notices
):
    """GET /counts/notices?user_id=... leaves out the notices the user dismissed"""
    with client as client:
        response = client.get(
            f"/counts/notices?user_id={TEST_USER_ID}", cookies=admin_jwt_cookie
        )

        assert response.status_code == 200
        assert response.json() == {"count": 4}


def test_admin_count_notices_by_min_start_utc(
    admin_jwt_cookie, client, inserted_notices
):
    """GET /counts/notices?min_start_utc=... counts only the notices starting on or after it"""
    min_start_utc = datetime.now(timezone.utc) + timedelta(hours=360)

    with client as client:
        response = client.get(
            "/counts/notices",
            params={"min_start_utc": min_start_utc.isoformat()},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert response.json() == {"count": 1}


def test_admin_count_notices_by_max_expires_utc(
    admin_jwt_cookie, client, inserted_notices
):
    """GET /counts/notices?max_expires_utc=... counts only the notices expiring on or before it"""
    max_expires_utc = datetime.now(timezone.utc) + timedelta(hours=9000)

    with client as client:
        response = client.get(
            "/counts/notices",
            params={"max_expires_utc": max_expires_utc.isoformat()},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert response.json() == {"count": 5}


def test_non_admin_counts_only_own_notices(user_jwt_cookie, client, inserted_notices):
    """GET /counts/notices by a non-admin ignores user_id and counts their own undismissed notices"""
    with client as client:
        response = client.get(
            f"/counts/notices?user_id={TEST_SUPERUSER_ID}", cookies=user_jwt_cookie
        )

        assert response.status_code == 200
        assert response.json() == {"count": 4}


def test_count_notices_by_type_and_read_status(
    user_jwt_cookie, client, inserted_notices
):
    """GET /counts/notices?type=...&is_read=... counts the matching notices"""
    with client as client:
        unread_custom = client.get(
            "/counts/notices?type=custom&is_read=false", cookies=user_jwt_cookie
        )
        read = client.get(
            "/counts/notices?is_read=true&include_dismissed=true",
            cookies=user_jwt_cookie,
        )

        assert unread_custom.json() == {"count": 2}
        assert read.json() == {"count": 1}


def test_unauthenticated_cannot_count_notices(client, inserted_notices):
    """GET /counts/notices requires a signed-in user"""
    with client as client:
        response = client.get("/counts/notices")

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
