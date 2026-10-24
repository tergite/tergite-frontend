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
import asyncio
from collections.abc import AsyncGenerator
from typing import Any, Callable, Generic, List, Optional, Set
from unittest.mock import MagicMock

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, Response
from httpx_oauth.oauth2 import OAuth2
from pydantic import BaseModel, Field, SecretStr
from pytest_mock import MockerFixture

from libs.authlib import exceptions, models, schemas
from libs.authlib.authentication import AuthenticationBackend, BearerTransport
from libs.authlib.authentication.strategy import Strategy
from libs.authlib.jwt import SecretType
from libs.authlib.manager import BaseUserManager
from libs.authlib.openapi import OpenAPIResponseType
from libs.storage import Database, Id, Schema, StorageSpec, generate_id
from tests._utils.storage import get_database_url, reset_database

IDType = str


class UserModel(Schema):
    __storage__ = StorageSpec(
        table="users", unique=("email",), case_insensitive=("email",)
    )

    id: Id = Field(default_factory=generate_id)
    email: str
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    roles: Set[str] = set()
    first_name: Optional[str] = None


class OAuthAccountModel(BaseModel):
    id: Id = Field(default_factory=generate_id)
    oauth_name: str
    access_token: str
    account_id: str
    account_email: str
    expires_at: Optional[int] = None
    refresh_token: Optional[str] = None


class UserOAuthModel(UserModel):
    __storage__ = StorageSpec(
        table="oauth_users",
        unique=("email",),
        case_insensitive=("email",),
        indexed_lists=("oauth_accounts",),
        indexes=(("oauth_accounts.oauth_name", "oauth_accounts.account_id"),),
    )

    oauth_accounts: List[OAuthAccountModel] = []


class User(schemas.BaseUser[IDType]):
    first_name: Optional[str] = None


class UserOAuth(User, schemas.BaseOAuthAccountMixin):
    pass


class BaseTestUserManager(Generic[models.UP], BaseUserManager[models.UP, IDType]):
    pass


class UserManager(BaseTestUserManager[UserModel]):
    pass


class UserManagerOAuth(BaseTestUserManager[UserOAuthModel]):
    pass


class UserManagerMock(BaseTestUserManager[models.UP]):
    get_by_email: MagicMock
    on_after_register: MagicMock
    on_after_login: MagicMock


AsyncMethodMocker = Callable[..., MagicMock]


@pytest.fixture
def async_method_mocker(mocker: MockerFixture) -> AsyncMethodMocker:
    def _async_method_mocker(
        object: Any,
        method: str,
        return_value: Any = None,
    ) -> MagicMock:
        mock: MagicMock = mocker.MagicMock()

        future: asyncio.Future = asyncio.Future()
        future.set_result(return_value)
        mock.return_value = future
        mock.side_effect = None

        setattr(object, method, mock)

        return mock

    return _async_method_mocker


@pytest.fixture(params=["SECRET", SecretStr("SECRET")])
def secret(request) -> SecretType:
    return request.param


@pytest.fixture
def user() -> UserModel:
    return UserModel(
        email="king.arthur@camelot.bt",
    )


@pytest.fixture
def user_oauth(
    oauth_account1: OAuthAccountModel, oauth_account2: OAuthAccountModel
) -> UserOAuthModel:
    return UserOAuthModel(
        email="king.arthur@camelot.bt",
        oauth_accounts=[oauth_account1, oauth_account2],
    )


@pytest.fixture
def inactive_user() -> UserModel:
    return UserModel(
        email="percival@camelot.bt",
        is_active=False,
    )


@pytest.fixture
def inactive_user_oauth(oauth_account3: OAuthAccountModel) -> UserOAuthModel:
    return UserOAuthModel(
        email="percival@camelot.bt",
        is_active=False,
        oauth_accounts=[oauth_account3],
    )


@pytest.fixture
def verified_user() -> UserModel:
    return UserModel(
        email="lake.lady@camelot.bt",
        is_active=True,
        is_verified=True,
    )


@pytest.fixture
def verified_user_oauth(oauth_account4: OAuthAccountModel) -> UserOAuthModel:
    return UserOAuthModel(
        email="lake.lady@camelot.bt",
        is_active=False,
        oauth_accounts=[oauth_account4],
    )


@pytest.fixture
def superuser() -> UserModel:
    return UserModel(
        email="merlin@camelot.bt",
        is_superuser=True,
        roles={"admin", "user"},
    )


@pytest.fixture
def superuser_oauth() -> UserOAuthModel:
    return UserOAuthModel(
        email="merlin@camelot.bt",
        is_superuser=True,
        oauth_accounts=[],
    )


@pytest.fixture
def verified_superuser() -> UserModel:
    return UserModel(
        email="the.real.merlin@camelot.bt",
        is_superuser=True,
        is_verified=True,
    )


@pytest.fixture
def verified_superuser_oauth() -> UserOAuthModel:
    return UserOAuthModel(
        email="the.real.merlin@camelot.bt",
        is_superuser=True,
        is_verified=True,
        oauth_accounts=[],
    )


@pytest.fixture
def oauth_account1() -> OAuthAccountModel:
    return OAuthAccountModel(
        oauth_name="service1",
        access_token="TOKEN",
        expires_at=1579000751,
        account_id="user_oauth1",
        account_email="king.arthur@camelot.bt",
    )


@pytest.fixture
def oauth_account2() -> OAuthAccountModel:
    return OAuthAccountModel(
        oauth_name="service2",
        access_token="TOKEN",
        expires_at=1579000751,
        account_id="user_oauth2",
        account_email="king.arthur@camelot.bt",
    )


@pytest.fixture
def oauth_account3() -> OAuthAccountModel:
    return OAuthAccountModel(
        oauth_name="service3",
        access_token="TOKEN",
        expires_at=1579000751,
        account_id="inactive_user_oauth1",
        account_email="percival@camelot.bt",
    )


@pytest.fixture
def oauth_account4() -> OAuthAccountModel:
    return OAuthAccountModel(
        oauth_name="service4",
        access_token="TOKEN",
        expires_at=1579000751,
        account_id="verified_user_oauth1",
        account_email="lake.lady@camelot.bt",
    )


@pytest.fixture
def oauth_account5() -> OAuthAccountModel:
    return OAuthAccountModel(
        oauth_name="service5",
        access_token="TOKEN",
        expires_at=1579000751,
        account_id="verified_superuser_oauth1",
        account_email="the.real.merlin@camelot.bt",
    )


@pytest.fixture
def user_database_kind() -> str:
    """SQLite; the modules that test how users are stored override it with every kind"""
    return "sqlite"


@pytest.fixture
async def database(user_database_kind, tmp_path) -> AsyncGenerator[Database, None]:
    database_url = get_database_url(user_database_kind, tmp_path)
    await reset_database(database_url)
    database = Database(database_url, schemas=[UserModel, UserOAuthModel])
    await database.setup()
    yield database
    await database.close()
    await reset_database(database_url)


@pytest.fixture
async def user_database(
    database: Database,
    user: UserModel,
    verified_user: UserModel,
    inactive_user: UserModel,
    superuser: UserModel,
    verified_superuser: UserModel,
) -> Database:
    await database.insert_many(
        UserModel, [user, verified_user, inactive_user, superuser, verified_superuser]
    )
    return database


@pytest.fixture
async def user_database_oauth(
    database: Database,
    user_oauth: UserOAuthModel,
    verified_user_oauth: UserOAuthModel,
    inactive_user_oauth: UserOAuthModel,
    superuser_oauth: UserOAuthModel,
    verified_superuser_oauth: UserOAuthModel,
) -> Database:
    await database.insert_many(
        UserOAuthModel,
        [
            user_oauth,
            verified_user_oauth,
            inactive_user_oauth,
            superuser_oauth,
            verified_superuser_oauth,
        ],
    )
    return database


@pytest.fixture
def make_user_manager(mocker: MockerFixture):
    def _make_user_manager(
        user_manager_class: type[BaseTestUserManager],
        database: Database,
        user_schema: type[UserModel],
    ):
        user_manager = user_manager_class(database, user_schema)
        mocker.spy(user_manager, "get_by_email")
        mocker.spy(user_manager, "on_after_register")
        mocker.spy(user_manager, "on_after_login")
        return user_manager

    return _make_user_manager


@pytest.fixture
def user_manager(make_user_manager, user_database):
    return make_user_manager(UserManager, user_database, UserModel)


@pytest.fixture
def user_manager_oauth(make_user_manager, user_database_oauth):
    return make_user_manager(UserManagerOAuth, user_database_oauth, UserOAuthModel)


@pytest.fixture
def get_user_manager(user_manager):
    def _get_user_manager():
        return user_manager

    return _get_user_manager


@pytest.fixture
def get_user_manager_oauth(user_manager_oauth):
    def _get_user_manager_oauth():
        return user_manager_oauth

    return _get_user_manager_oauth


class MockTransport(BearerTransport):
    def __init__(self, tokenUrl: str):
        super().__init__(tokenUrl)

    async def get_logout_response(self) -> Any:
        return Response()

    @staticmethod
    def get_openapi_logout_responses_success() -> OpenAPIResponseType:
        return {}


class MockStrategy(Strategy[UserModel, IDType]):
    async def read_token(
        self, token: Optional[str], user_manager: BaseUserManager[UserModel, IDType]
    ) -> Optional[UserModel]:
        if token is not None:
            try:
                parsed_id = user_manager.parse_id(token)
                return await user_manager.get(parsed_id)
            except (exceptions.InvalidID, exceptions.UserNotExists):
                return None
        return None

    async def write_token(self, user: UserModel) -> str:
        return str(user.id)

    async def destroy_token(self, token: str, user: UserModel) -> None:
        return None


def get_mock_authentication(name: str):
    return AuthenticationBackend(
        name=name,
        transport=MockTransport(tokenUrl="/login"),
        get_strategy=lambda: MockStrategy(),
    )


@pytest.fixture
def mock_authentication():
    return get_mock_authentication(name="mock")


@pytest.fixture
def get_test_client():
    async def _get_test_client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
        async with LifespanManager(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://app.io"
            ) as test_client:
                yield test_client

    return _get_test_client


@pytest.fixture
def oauth_client() -> OAuth2:
    CLIENT_ID = "CLIENT_ID"
    CLIENT_SECRET = "CLIENT_SECRET"
    AUTHORIZE_ENDPOINT = "https://www.camelot.bt/authorize"
    ACCESS_TOKEN_ENDPOINT = "https://www.camelot.bt/access-token"

    return OAuth2(
        CLIENT_ID,
        CLIENT_SECRET,
        AUTHORIZE_ENDPOINT,
        ACCESS_TOKEN_ENDPOINT,
        name="service1",
    )
