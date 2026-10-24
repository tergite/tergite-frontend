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
from collections.abc import AsyncGenerator, Sequence
from typing import Generic, Optional

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, Request, status
from fastapi.security.base import SecurityBase

from libs.authlib import models
from libs.authlib.authentication import AuthenticationBackend, Authenticator
from libs.authlib.authentication.authenticator import DuplicateBackendNamesError
from libs.authlib.authentication.strategy import Strategy
from libs.authlib.authentication.transport import Transport
from libs.authlib.manager import BaseUserManager
from libs.authlib.types import DependencyCallable
from tests.libs.authlib.conftest import User, UserModel


class MockSecurityScheme(SecurityBase):
    def __call__(self, request: Request) -> Optional[str]:
        return "mock"


class MockTransport(Transport):
    scheme: MockSecurityScheme

    def __init__(self):
        self.scheme = MockSecurityScheme()


class NoneStrategy(Strategy):
    async def read_token(
        self, token: Optional[str], user_manager: BaseUserManager[models.UP, models.ID]
    ) -> Optional[models.UP]:
        return None


class UserStrategy(Strategy, Generic[models.UP]):
    def __init__(self, user: models.UP):
        self.user = user

    async def read_token(
        self, token: Optional[str], user_manager: BaseUserManager[models.UP, models.ID]
    ) -> Optional[models.UP]:
        return self.user

    def get_user_id(self, token: Optional[str]) -> Optional[str]:
        return self.user.id


@pytest.fixture
def get_backend_none():
    def _get_backend_none(name: str = "none"):
        return AuthenticationBackend(
            name=name, transport=MockTransport(), get_strategy=lambda: NoneStrategy()
        )

    return _get_backend_none


@pytest.fixture
def get_backend_user(user: UserModel):
    def _get_backend_user(token_user: Optional[UserModel] = None, name: str = "user"):
        return AuthenticationBackend(
            name=name,
            transport=MockTransport(),
            get_strategy=lambda: UserStrategy(token_user or user),
        )

    return _get_backend_user


@pytest_asyncio.fixture
def get_test_auth_client(get_user_manager, get_test_client):
    async def _get_test_auth_client(
        backends: list[AuthenticationBackend],
        get_enabled_backends: Optional[
            DependencyCallable[Sequence[AuthenticationBackend]]
        ] = None,
    ) -> AsyncGenerator[httpx.AsyncClient, None]:
        app = FastAPI()
        authenticator = Authenticator(backends, get_user_manager)

        @app.get("/test-current-user", response_model=User)
        def test_current_user(
            user: UserModel = Depends(
                authenticator.current_user(get_enabled_backends=get_enabled_backends)
            ),
        ):
            return user

        @app.get("/test-current-active-user", response_model=User)
        def test_current_active_user(
            user: UserModel = Depends(
                authenticator.current_user(
                    active=True, get_enabled_backends=get_enabled_backends
                )
            ),
        ):
            return user

        @app.get("/test-current-superuser", response_model=User)
        def test_current_superuser(
            user: UserModel = Depends(
                authenticator.current_user(
                    active=True,
                    superuser=True,
                    get_enabled_backends=get_enabled_backends,
                )
            ),
        ):
            return user

        @app.get("/test-current-admin", response_model=User)
        def test_current_admin(
            user: UserModel = Depends(authenticator.current_user(roles=("admin",))),
        ):
            return user

        @app.get("/test-current-user-id")
        def test_current_user_id(
            user_id: str = Depends(
                authenticator.get_current_user_id(
                    get_enabled_backends=get_enabled_backends
                )
            ),
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

    return _get_test_auth_client


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_authenticator(get_test_auth_client, get_backend_none, get_backend_user):
    async for client in get_test_auth_client([get_backend_none(), get_backend_user()]):
        response = await client.get("/test-current-user")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_authenticator_none(get_test_auth_client, get_backend_none):
    async for client in get_test_auth_client(
        [get_backend_none(), get_backend_none(name="none-bis")]
    ):
        response = await client.get("/test-current-user")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_authenticator_none_enabled(
    get_test_auth_client, get_backend_none, get_backend_user
):
    backend_none = get_backend_none()
    backend_user = get_backend_user()

    async def get_enabled_backends():
        return [backend_none]

    async for client in get_test_auth_client(
        [backend_none, backend_user], get_enabled_backends
    ):
        response = await client.get("/test-current-user")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_a_user_without_a_required_role_is_forbidden(
    get_test_auth_client, get_backend_user
):
    async for client in get_test_auth_client([get_backend_user()]):
        response = await client.get("/test-current-admin")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_a_user_with_a_required_role_passes(
    get_test_auth_client, get_backend_user, superuser
):
    async for client in get_test_auth_client([get_backend_user(superuser)]):
        response = await client.get("/test-current-admin")
        assert response.json()["id"] == superuser.id


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_current_user_id_is_read_from_the_token(
    get_test_auth_client, get_backend_none, get_backend_user, user
):
    async for client in get_test_auth_client([get_backend_none(), get_backend_user()]):
        response = await client.get("/test-current-user-id")
        assert response.json() == user.id


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_current_user_id_without_one(get_test_auth_client, get_backend_none):
    async for client in get_test_auth_client([get_backend_none()]):
        response = await client.get("/test-current-user-id")
        optional_response = await client.get("/test-optional-current-user-id")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert optional_response.json() is None


@pytest.mark.authentication
@pytest.mark.asyncio
async def test_authenticators_with_same_name(get_test_auth_client, get_backend_none):
    with pytest.raises(DuplicateBackendNamesError):
        async for _ in get_test_auth_client([get_backend_none(), get_backend_none()]):
            pass
