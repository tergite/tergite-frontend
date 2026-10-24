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
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, status

from libs.authlib.fastapi_users import FastAPIUsers
from libs.authlib.providers import OAuthProvider
from tests.libs.authlib.conftest import IDType, UserModel


@pytest.fixture
def fastapi_users(get_user_manager, mock_authentication) -> FastAPIUsers:
    return FastAPIUsers[UserModel, IDType](get_user_manager, [mock_authentication])


@pytest.fixture
def test_app(
    fastapi_users: FastAPIUsers, secret, mock_authentication, oauth_client
) -> FastAPI:
    app = FastAPI()
    app.include_router(fastapi_users.get_auth_router(mock_authentication))
    app.include_router(
        fastapi_users.get_oauth_router(
            {"service1": OAuthProvider(client=oauth_client)},
            mock_authentication,
            secret,
        )
    )

    return app


@pytest_asyncio.fixture
async def test_app_client(test_app, get_test_client):
    async for client in get_test_client(test_app):
        yield client


@pytest.fixture
def openapi_dict(test_app: FastAPI):
    return test_app.openapi()


@pytest.mark.asyncio
@pytest.mark.openapi
async def test_openapi_route(test_app_client: httpx.AsyncClient):
    response = await test_app_client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK


class TestOAuth2:
    def test_oauth_authorize_status_codes(self, openapi_dict):
        route = openapi_dict["paths"]["/{provider}/authorize"]["get"]
        assert list(route["responses"].keys()) == ["200", "422"]

    def test_oauth_callback_status_codes(self, openapi_dict):
        route = openapi_dict["paths"]["/{provider}/callback"]["get"]
        assert set(route["responses"]) == {"200", "204", "307", "400", "422"}
