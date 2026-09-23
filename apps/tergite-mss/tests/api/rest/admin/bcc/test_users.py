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

from typing import List

import pytest

from tests._utils.auth import TEST_USER_ID
from tests._utils.fixtures import load_json_fixture
from tests._utils.mock_backend import BCC_USERS
from tests._utils.records import PaginationInfo, paginate
from tests.conftest import BACKEND_SLUGS

_BCC_USERS = load_json_fixture("bcc_users.json")

_PAGINATION: List["PaginationInfo"] = load_json_fixture("pagination.json")

_BCC_USERS_VIEW_PARAMS = [
    (backend, pagination) for backend in BACKEND_SLUGS for pagination in _PAGINATION
]
_BCC_USERS_CREATE_PARAMS = [
    (backend, payload) for backend in BACKEND_SLUGS for payload in _BCC_USERS
]


@pytest.mark.parametrize("backend, user_payload", _BCC_USERS_CREATE_PARAMS)
def test_admin_create_bcc_user(
    client, backend, user_payload, user_jwt_cookie, admin_jwt_cookie, mock_bcc
):
    """POST to '/admin/bcc-users' by admins should create the user via MSS"""
    with client as client:
        payload = {**user_payload, "id": TEST_USER_ID}
        # non admins are not allowed
        response = client.post(
            f"/admin/bcc-users/{backend}", cookies=user_jwt_cookie, json=payload
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.post(
            f"/admin/bcc-users/{backend}", cookies=admin_jwt_cookie, json=payload
        )
        expected = {
            "id": TEST_USER_ID,
            "name": user_payload["name"],
            "email": user_payload["email"],
            "is_admin": False,
        }

        assert response.status_code == 200
        assert response.json() == expected


@pytest.mark.parametrize("backend, pagination", _BCC_USERS_VIEW_PARAMS)
def test_admin_view_bcc_users(
    client, admin_jwt_cookie, user_jwt_cookie, backend, pagination, mock_bcc
):
    """GET '/admin/bcc-users/{backend}' should show to an admin the paginated list of user profiles via MSS"""
    with client as client:
        params = {k: v for k, v in pagination.items() if v is not None}
        # non admins are not allowed
        response = client.get(
            f"/admin/bcc-users/{backend}/", cookies=user_jwt_cookie, params=params
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.get(
            f"/admin/bcc-users/{backend}/", cookies=admin_jwt_cookie, params=params
        )
        actual_output = response.json()

        skip = pagination["skip"]
        limit = pagination["limit"]

        expected = paginate(BCC_USERS, skip=skip, limit=limit)

        assert response.status_code == 200
        assert actual_output == expected


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_remove_bcc_user(client, backend, admin_jwt_cookie, mock_bcc):
    """DELETE '/admin/bcc-users/{backend}/{user_id}' by admin removes the user via MSS"""
    with client as client:
        url = f"/admin/bcc-users/{backend}/USER_ID_PLACEHOLDER"
        response = client.delete(url, cookies=admin_jwt_cookie)
        assert response.status_code == 200
        assert response.json() == {"status": "success", "detail": f"User deleted"}


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_non_admin_remove_user(client, backend, user_jwt_cookie, mock_bcc):
    """Non admin cannot remove the profile of any user"""
    with client as client:
        url = f"/admin/bcc-users/{backend}/USER_ID_PLACEHOLDER"
        response = client.delete(url, cookies=user_jwt_cookie)
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}
