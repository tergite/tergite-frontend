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

"""Tests that error responses stay usable by a browser"""
import pytest

from api.rest import app

_ORIGIN = "http://127.0.0.1:3000"
_PATH = "/_raises_for_test"


class _Unregistered(Exception):
    """A type with no exception handler of its own, as pymongo's errors are"""


@pytest.fixture()
def raising_route():
    """Adds a route that blows up in a way no exception handler covers"""

    @app.get(_PATH, include_in_schema=False)
    async def _raise():
        raise _Unregistered("boom")

    yield
    app.router.routes = [
        route for route in app.router.routes if getattr(route, "path", None) != _PATH
    ]


def test_unhandled_error_is_a_500(client, raising_route):
    with client as client:
        response = client.get(_PATH, headers={"Origin": _ORIGIN})

        assert response.status_code == 500
        assert response.json() == {"detail": "Unexpected server error"}


def test_unhandled_error_keeps_its_cors_headers(client, raising_route):
    """Without these the browser reports a CORS failure and hides the real error

    Starlette hands `Exception` to ServerErrorMiddleware, which wraps CORS, so the 500 it
    writes carries no access-control-allow-origin.
    """
    with client as client:
        response = client.get(_PATH, headers={"Origin": _ORIGIN})

        assert response.headers["access-control-allow-origin"] == _ORIGIN


def test_handled_error_keeps_its_cors_headers(client):
    """The registered handlers run inside CORS already; guard against a reordering"""
    with client as client:
        response = client.get("/devices/no-such-device", headers={"Origin": _ORIGIN})

        assert response.status_code == 404
        assert response.headers["access-control-allow-origin"] == _ORIGIN
