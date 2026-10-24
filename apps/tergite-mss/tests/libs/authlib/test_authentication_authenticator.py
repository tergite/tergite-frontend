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
from typing import Dict, Optional

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, status

from libs.authlib import models
from libs.authlib.authentication import Authenticator
from libs.authlib.authentication.strategy import Strategy
from libs.authlib.manager import BaseUserManager
from tests.libs.authlib.conftest import User, UserModel

_COOKIE_NAME = "session"


class TokenStrategy(Strategy):
    """Reads each token into the user it is mapped to"""

    def __init__(self, users_by_token: Dict[str, models.UP]):
        self.users_by_token = users_by_token

    async def read_token(
        self, token: Optional[str], user_manager: BaseUserManager[models.UP, models.ID]
    ) -> Optional[models.UP]:
        return self.users_by_token.get(token)

    def get_user_id(self, token: Optional[str]) -> Optional[str]:
        user = self.users_by_token.get(token)
        return None if user is None else user.id


@pytest_asyncio.fixture
async def test_auth_client(
    get_user_manager, get_test_client, user: UserModel, superuser: UserModel
) -> AsyncGenerator[httpx.AsyncClient, None]:
    strategy = TokenStrategy({"user-token": user, "superuser-token": superuser})
    authenticator = Authenticator(get_user_manager, lambda: strategy, _COOKIE_NAME)
    app = FastAPI()

    @app.get("/test-current-user", response_model=User)
    def test_current_user(user: UserModel = Depends(authenticator.current_user())):
        return user

    @app.get("/test-current-admin", response_model=User)
    def test_current_admin(
        user: UserModel = Depends(authenticator.current_user(roles=("admin",))),
    ):
        return user

    @app.get("/test-current-user-id")
    def test_current_user_id(
        user_id: str = Depends(authenticator.get_current_user_id()),
    ):
        return user_id

    @app.get("/test-optional-current-user-id")
    def test_optional_current_user_id(
        user_id: Optional[str] = Depends(
            authenticator.get_current_user_id(is_optional=True)
        ),
    ):
        return user_id

    async for client in get_test_client(app):
        yield client


@pytest.mark.authentication
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers, cookies",
    [
        ({"Authorization": "Bearer user-token"}, {}),
        ({}, {_COOKIE_NAME: "user-token"}),
        ({"Authorization": "Bearer unknown-token"}, {_COOKIE_NAME: "user-token"}),
    ],
    ids=["bearer", "cookie", "bad-bearer-then-cookie"],
)
async def test_a_token_in_the_header_or_cookie_finds_the_user(
    test_auth_client: httpx.AsyncClient, user: UserModel, headers, cookies
):
    test_auth_client.cookies.update(cookies)
    response = await test_auth_client.get("/test-current-user", headers=headers)

    assert response.json()["id"] == user.id


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_no_known_token_is_unauthorized(test_auth_client: httpx.AsyncClient):
    missing = await test_auth_client.get("/test-current-user")
    unknown = await test_auth_client.get(
        "/test-current-user", headers={"Authorization": "Bearer unknown-token"}
    )

    assert missing.status_code == status.HTTP_401_UNAUTHORIZED
    assert unknown.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_a_user_without_a_required_role_is_forbidden(
    test_auth_client: httpx.AsyncClient,
):
    response = await test_auth_client.get(
        "/test-current-admin", headers={"Authorization": "Bearer user-token"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_a_user_with_a_required_role_passes(
    test_auth_client: httpx.AsyncClient, superuser: UserModel
):
    response = await test_auth_client.get(
        "/test-current-admin", headers={"Authorization": "Bearer superuser-token"}
    )

    assert response.json()["id"] == superuser.id


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_current_user_id_is_read_from_the_token(
    test_auth_client: httpx.AsyncClient, user: UserModel
):
    test_auth_client.cookies.update({_COOKIE_NAME: "user-token"})
    response = await test_auth_client.get("/test-current-user-id")

    assert response.json() == user.id


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_current_user_id_without_one(test_auth_client: httpx.AsyncClient):
    response = await test_auth_client.get("/test-current-user-id")
    optional_response = await test_auth_client.get("/test-optional-current-user-id")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert optional_response.json() is None
