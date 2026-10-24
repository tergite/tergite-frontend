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
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, status

from libs.authlib.authentication import Authenticator
from libs.authlib.router import get_auth_router
from tests.libs.authlib.conftest import UserModel, get_mock_authentication


@pytest.fixture
def app_factory(get_user_manager, mock_authentication):
    def _app_factory(requires_verification: bool) -> FastAPI:
        mock_authentication_bis = get_mock_authentication(name="mock-bis")
        authenticator = Authenticator(
            get_user_manager, mock_authentication.get_strategy
        )

        mock_auth_router = get_auth_router(
            mock_authentication,
            authenticator,
            requires_verification=requires_verification,
        )
        mock_bis_auth_router = get_auth_router(
            mock_authentication_bis,
            authenticator,
            requires_verification=requires_verification,
        )

        app = FastAPI()
        app.include_router(mock_auth_router, prefix="/mock")
        app.include_router(mock_bis_auth_router, prefix="/mock-bis")

        return app

    return _app_factory


@pytest_asyncio.fixture(
    params=[True, False], ids=["required_verification", "not_required_verification"]
)
async def test_app_client(
    request, get_test_client, app_factory
) -> AsyncGenerator[tuple[httpx.AsyncClient, bool], None]:
    requires_verification = request.param
    app = app_factory(requires_verification)

    async for client in get_test_client(app):
        yield client, requires_verification


@pytest.mark.router
@pytest.mark.parametrize("path", ["/mock/logout", "/mock-bis/logout"])
@pytest.mark.asyncio
class TestLogout:
    async def test_missing_token(
        self,
        path,
        test_app_client: tuple[httpx.AsyncClient, bool],
    ):
        client, _ = test_app_client
        response = await client.post(path)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_valid_credentials_unverified(
        self,
        mocker,
        path,
        test_app_client: tuple[httpx.AsyncClient, bool],
        user: UserModel,
    ):
        client, requires_verification = test_app_client
        response = await client.post(
            path, headers={"Authorization": f"Bearer {user.id}"}
        )
        if requires_verification:
            assert response.status_code == status.HTTP_403_FORBIDDEN
        else:
            assert response.status_code == status.HTTP_200_OK

    async def test_valid_credentials_verified(
        self,
        mocker,
        path,
        test_app_client: tuple[httpx.AsyncClient, bool],
        verified_user: UserModel,
    ):
        client, _ = test_app_client
        response = await client.post(
            path, headers={"Authorization": f"Bearer {verified_user.id}"}
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
@pytest.mark.router
async def test_route_names(app_factory, mock_authentication):
    app = app_factory(False)
    logout_route_name = f"auth:{mock_authentication.name}.logout"
    assert app.url_path_for(logout_route_name) == "/mock/logout"
