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
"""Users in a real Database, an OAuth provider, and the Auth they make up"""
from collections.abc import AsyncGenerator
from typing import List, Set

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx_oauth.oauth2 import OAuth2
from pydantic import Field

from libs.authlib import Auth, BaseOAuthAccount, OAuthProvider, SessionCookie
from libs.storage import Database, Id, Schema, StorageSpec, generate_id
from tests._utils.storage import get_database_url, reset_database

SECRET = "SECRET"
COOKIE_NAME = "session"
SESSION_LIFETIME_SECONDS = 3600


class UserModel(Schema):
    __storage__ = StorageSpec(
        table="users",
        unique=("email",),
        case_insensitive=("email",),
        indexed_lists=("oauth_accounts",),
        indexes=(("oauth_accounts.oauth_name", "oauth_accounts.account_id"),),
    )

    id: Id = Field(default_factory=generate_id)
    email: str
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    roles: Set[str] = {"user"}
    oauth_accounts: List[BaseOAuthAccount] = []


@pytest.fixture
def user_database_kind() -> str:
    """SQLite; the modules that test how users are stored override it with every kind"""
    return "sqlite"


@pytest.fixture
async def database(user_database_kind, tmp_path) -> AsyncGenerator[Database, None]:
    database_url = get_database_url(user_database_kind, tmp_path)
    await reset_database(database_url)
    database = Database(database_url, schemas=[UserModel])
    await database.setup()
    yield database
    await database.close()
    await reset_database(database_url)


@pytest.fixture
def user() -> UserModel:
    return UserModel(
        email="king.arthur@camelot.bt",
        is_verified=True,
        oauth_accounts=[_get_account("user_oauth1", "king.arthur@camelot.bt")],
    )


@pytest.fixture
def inactive_user() -> UserModel:
    return UserModel(
        email="percival@camelot.bt",
        is_active=False,
        oauth_accounts=[_get_account("inactive_oauth1", "percival@camelot.bt")],
    )


@pytest.fixture
def unverified_user() -> UserModel:
    return UserModel(email="lake.lady@camelot.bt")


@pytest.fixture
def superuser() -> UserModel:
    return UserModel(
        email="merlin@camelot.bt",
        is_superuser=True,
        is_verified=True,
        roles={"admin"},
    )


@pytest.fixture
async def user_database(
    database: Database,
    user: UserModel,
    inactive_user: UserModel,
    unverified_user: UserModel,
    superuser: UserModel,
) -> Database:
    await database.insert_many(
        UserModel, [user, inactive_user, unverified_user, superuser]
    )
    return database


@pytest.fixture
def oauth_client() -> OAuth2:
    return OAuth2(
        "CLIENT_ID",
        "CLIENT_SECRET",
        "https://www.camelot.bt/authorize",
        "https://www.camelot.bt/access-token",
        name="service1",
    )


@pytest.fixture
def provider(oauth_client: OAuth2) -> OAuthProvider:
    return OAuthProvider(
        client=oauth_client, email_regex=r".*@camelot\.bt$", roles=("researcher",)
    )


@pytest.fixture
def logged_in_users() -> List[UserModel]:
    return []


@pytest.fixture
def auth(
    user_database: Database, provider: OAuthProvider, logged_in_users: List[UserModel]
) -> Auth:
    async def on_after_login(database: Database, logged_in_user: UserModel) -> None:
        logged_in_users.append(logged_in_user)

    return Auth(
        lambda: user_database,
        UserModel,
        providers={"service1": provider},
        secret=SECRET,
        session_lifetime_seconds=SESSION_LIFETIME_SECONDS,
        cookie=SessionCookie(name=COOKIE_NAME),
        on_after_login=on_after_login,
    )


@pytest.fixture
def get_test_client():
    async def _get_test_client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
        async with LifespanManager(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://app.io"
            ) as test_client:
                yield test_client

    return _get_test_client


def _get_account(account_id: str, email: str) -> BaseOAuthAccount:
    return BaseOAuthAccount(
        oauth_name="service1",
        access_token="TOKEN",
        expires_at=1579000751,
        account_id=account_id,
        account_email=email,
    )
