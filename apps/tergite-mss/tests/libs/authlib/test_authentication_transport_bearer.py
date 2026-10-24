# This code is part of Tergite
#
# (C) Copyright François Voron 2019 (fastapi-users 14.0.2, MIT licence; see libs/authlib/LICENSE)
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import pytest
from fastapi import status
from fastapi.responses import JSONResponse

from libs.authlib.authentication.transport import (
    BearerTransport,
    TransportLogoutNotSupportedError,
)
from libs.authlib.authentication.transport.bearer import BearerResponse


@pytest.fixture()
def bearer_transport() -> BearerTransport:
    return BearerTransport(tokenUrl="/login")


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_get_login_response(bearer_transport: BearerTransport):
    response = await bearer_transport.get_login_response("TOKEN")

    assert isinstance(response, JSONResponse)
    assert response.body == b'{"access_token":"TOKEN","token_type":"bearer"}'


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_get_logout_response(bearer_transport: BearerTransport):
    with pytest.raises(TransportLogoutNotSupportedError):
        await bearer_transport.get_logout_response()


@pytest.mark.authentication
@pytest.mark.openapi
def test_get_openapi_login_responses_success(bearer_transport: BearerTransport):
    openapi_responses = bearer_transport.get_openapi_login_responses_success()
    assert openapi_responses[status.HTTP_200_OK]["model"] == BearerResponse


@pytest.mark.authentication
@pytest.mark.openapi
def test_get_openapi_logout_responses_success(bearer_transport: BearerTransport):
    openapi_responses = bearer_transport.get_openapi_logout_responses_success()
    assert openapi_responses == {}
