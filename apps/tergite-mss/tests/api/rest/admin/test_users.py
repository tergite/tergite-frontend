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

from tests._utils.auth import TEST_USER_EMAIL

_USER_EMAILS_URL = "/admin/user-emails/"


def test_admin_get_user_emails(client, admin_jwt_cookie):
    """Admins can look up user emails at /admin/user-emails/, addresses alone"""
    with client as client:
        response = client.get(_USER_EMAILS_URL, cookies=admin_jwt_cookie)

        got = response.json()
        assert response.status_code == 200
        assert TEST_USER_EMAIL in got
        assert all(isinstance(item, str) for item in got)
        assert got == sorted(got)


def test_admin_search_user_emails(client, admin_jwt_cookie):
    """Typing part of an address is the whole point of the endpoint"""
    with client as client:
        response = client.get(
            f"{_USER_EMAILS_URL}?search=OHN.D", cookies=admin_jwt_cookie
        )

        assert response.json() == [TEST_USER_EMAIL]


def test_admin_search_user_emails_is_not_a_regex(client, admin_jwt_cookie):
    """A regex in the query must be matched as text, not evaluated"""
    with client as client:
        response = client.get(
            f"{_USER_EMAILS_URL}?search=.%2B%40", cookies=admin_jwt_cookie
        )

        assert response.json() == []


def test_admin_get_user_emails_limited(client, admin_jwt_cookie):
    """The page size is the caller's to set"""
    with client as client:
        response = client.get(f"{_USER_EMAILS_URL}?limit=1", cookies=admin_jwt_cookie)

        assert len(response.json()) == 1


def test_non_admin_cannot_get_user_emails(client, user_jwt_cookie):
    """A directory of addresses is not for every logged-in user"""
    with client as client:
        response = client.get(_USER_EMAILS_URL, cookies=user_jwt_cookie)

        assert response.status_code == 403


def test_unauthenticated_get_user_emails(client):
    """Anonymous callers get nothing"""
    with client as client:
        response = client.get(_USER_EMAILS_URL)

        assert response.status_code == 401
