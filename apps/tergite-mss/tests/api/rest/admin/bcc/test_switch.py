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

import httpx
import pytest

from tests._utils.env import TEST_BACKENDS_MAP
from tests.conftest import BACKEND_SLUGS


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_switch_off(client, admin_jwt_cookie, user_jwt_cookie, backend, mock_bcc):
    """POST '/admin/bcc/switch/{backend}/off' switches off the backend via MSS"""
    with client as client:
        # non admins are not allowed
        response = client.post(
            f"/admin/bcc/switch/{backend}/off", cookies=user_jwt_cookie
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.post(
            f"/admin/bcc/switch/{backend}/off", cookies=admin_jwt_cookie
        )
        actual_output = response.json()

        assert response.status_code == 200
        assert actual_output == {"status": "success"}


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_switch_off_relays_a_bcc_error(
    client, admin_jwt_cookie, backend, mock_bcc
):
    """A BCC error reaches the client with the BCC's status code and message"""
    mock_bcc.post(f"{TEST_BACKENDS_MAP[backend]['url']}/switch/off").mock(
        return_value=httpx.Response(409, json={"detail": "already off"})
    )

    with client as client:
        response = client.post(
            f"/admin/bcc/switch/{backend}/off", cookies=admin_jwt_cookie
        )

        assert response.status_code == 409
        assert response.json() == {"detail": "already off"}


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_switch_on(client, admin_jwt_cookie, user_jwt_cookie, backend, mock_bcc):
    """POST '/admin/bcc/switch/{backend}/on' switches on the backend via MSS"""
    with client as client:
        # non admins are not allowed
        response = client.post(
            f"/admin/bcc/switch/{backend}/on", cookies=user_jwt_cookie
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.post(
            f"/admin/bcc/switch/{backend}/on", cookies=admin_jwt_cookie
        )
        actual_output = response.json()

        assert response.status_code == 200
        assert actual_output == {"status": "success"}
