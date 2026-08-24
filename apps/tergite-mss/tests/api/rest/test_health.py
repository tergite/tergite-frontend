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

"""Tests for the container healthcheck endpoint"""
from loguru import logger


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
