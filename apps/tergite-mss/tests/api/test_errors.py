# This code is part of Tergite
#
# (C) Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Tests for the exception handlers of the REST API"""
from typing import List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.errors import make_exception_group_handler, make_http_error_handler
from utils.exc import ConflictError, NotFoundError


@pytest.mark.parametrize(
    "errors, status_code, detail",
    [
        ([ConflictError("taken")], 409, "taken"),
        ([NotFoundError("missing")], 404, "missing"),
        ([ValueError("oops")], 500, "Unexpected server error"),
        (
            [ConflictError("taken"), NotFoundError("missing")],
            500,
            "Unexpected server error",
        ),
    ],
)
def test_exception_group_handler(errors: List[Exception], status_code, detail):
    """An exception group of one error answers as that error, of several as unexpected"""
    client = TestClient(_get_app(ExceptionGroup("errors", errors)))

    response = client.get("/")

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def _get_app(error: Exception) -> FastAPI:
    """Gets an app whose only route raises the given error"""
    app = FastAPI()
    app.add_exception_handler(NotFoundError, make_http_error_handler(404))
    app.add_exception_handler(ConflictError, make_http_error_handler(409))
    app.add_exception_handler(
        Exception, make_http_error_handler(500, "Unexpected server error")
    )
    app.add_exception_handler(
        ExceptionGroup, make_exception_group_handler(app.exception_handlers)
    )

    @app.get("/")
    async def raise_error():
        raise error

    return app
