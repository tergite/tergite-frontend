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

"""Tests for the superuser-only email lookup behind the admin project forms"""
from tests._utils.auth import TEST_USER_EMAIL

_URL = "/admin/user-emails/"


def test_superuser_gets_addresses(client, admin_jwt_cookie):
    """The list is addresses alone, never user records"""
    with client as client:
        response = client.get(_URL, cookies=admin_jwt_cookie)

        got = response.json()
        assert response.status_code == 200
        assert TEST_USER_EMAIL in got
        assert all(isinstance(item, str) for item in got)


def test_addresses_come_back_sorted(client, admin_jwt_cookie):
    with client as client:
        got = client.get(_URL, cookies=admin_jwt_cookie).json()

        assert got == sorted(got)


def test_search_matches_a_substring_of_the_address(client, admin_jwt_cookie):
    """Typing part of an address is the whole point of the endpoint"""
    with client as client:
        got = client.get(f"{_URL}?search=OHN.D", cookies=admin_jwt_cookie).json()

        assert got == [TEST_USER_EMAIL]


def test_search_treats_the_query_as_text(client, admin_jwt_cookie):
    """A regex in the query must not be evaluated as one"""
    with client as client:
        got = client.get(f"{_URL}?search=.%2B%40", cookies=admin_jwt_cookie).json()

        assert got == []


def test_limit_caps_the_page(client, admin_jwt_cookie):
    with client as client:
        got = client.get(f"{_URL}?limit=1", cookies=admin_jwt_cookie).json()

        assert len(got) == 1


def test_ordinary_user_is_refused(client, user_jwt_cookie):
    """A directory of addresses is not for every logged-in user"""
    with client as client:
        response = client.get(_URL, cookies=user_jwt_cookie)

        assert response.status_code == 403


def test_anonymous_is_refused(client):
    with client as client:
        response = client.get(_URL)

        assert response.status_code == 401
