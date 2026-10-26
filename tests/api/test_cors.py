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
"""CORS answers that the dashboard's credentialed requests depend on"""

_ORIGIN = "http://dashboard.example.com"


def test_credentialed_request_gets_its_origin_back(client, user_jwt_cookie):
    """A request with an Origin is answered with that origin, never '*', and credentials allowed"""
    with client as client:
        response = client.get(
            "/me/profile", headers={"Origin": _ORIGIN}, cookies=user_jwt_cookie
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_preflight_gets_its_origin_back(client):
    """A preflight request is answered with the asking origin and credentials allowed"""
    with client as client:
        response = client.options(
            "/me/profile",
            headers={"Origin": _ORIGIN, "Access-Control-Request-Method": "GET"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
