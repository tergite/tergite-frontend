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
"""Integration tests for the app itself: its middleware and its unrouted endpoints"""
import pytest
from loguru import logger

from api.rest import app

_ORIGIN = "http://127.0.0.1:3000"
_RAISING_PATH = "/_raises_for_test"


class _UnregisteredError(Exception):
    """A type with no exception handler of its own, as pymongo's errors are"""


@pytest.fixture()
def raising_route():
    """Adds a route that blows up in a way no exception handler covers"""

    @app.get(_RAISING_PATH, include_in_schema=False)
    async def _raise():
        raise _UnregisteredError("boom")

    yield
    app.router.routes = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) != _RAISING_PATH
    ]


def test_health_needs_no_credentials(client):
    """The container probe has no cookie and no app token"""
    with client as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_health_is_not_logged(client):
    """A ten-second probe must not fill the request log

    loguru does not propagate to caplog, so the assertion needs its own sink.
    """
    lines = []
    sink_id = logger.add(lines.append, level="DEBUG")
    try:
        with client as client:
            client.get("/health")
            client.get("/devices/")
    finally:
        logger.remove(sink_id)

    logged = " ".join(lines)
    # the /devices/ line proves the sink is actually capturing
    assert "/devices/" in logged
    assert "/health" not in logged


def test_unhandled_error_is_a_500(client, raising_route):
    """An error with no handler of its own still gets a tidy response"""
    with client as client:
        response = client.get(_RAISING_PATH, headers={"Origin": _ORIGIN})

        assert response.status_code == 500
        assert response.json() == {"detail": "Unexpected server error"}


def test_unhandled_error_keeps_its_cors_headers(client, raising_route):
    """Without these the browser reports a CORS failure and hides the real error

    Starlette hands `Exception` to ServerErrorMiddleware, which wraps CORS, so the 500 it
    writes carries no access-control-allow-origin.
    """
    with client as client:
        response = client.get(_RAISING_PATH, headers={"Origin": _ORIGIN})

        assert response.headers["access-control-allow-origin"] == _ORIGIN


def test_handled_error_keeps_its_cors_headers(client):
    """The registered handlers run inside CORS already; guard against a reordering"""
    with client as client:
        response = client.get("/devices/no-such-device", headers={"Origin": _ORIGIN})

        assert response.status_code == 404
        assert response.headers["access-control-allow-origin"] == _ORIGIN
