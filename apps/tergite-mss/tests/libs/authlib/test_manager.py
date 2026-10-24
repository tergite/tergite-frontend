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

from libs.authlib.exceptions import (
    EmailNotPermitted,
    UnsupportedProvider,
    UserAlreadyExists,
    UserNotExists,
)
from libs.authlib.providers import ProviderRules
from libs.storage import generate_id
from tests.libs.authlib.conftest import (
    UserManager,
    UserManagerMock,
    UserManagerOAuth,
    UserModel,
    UserOAuthModel,
)


@pytest.fixture(params=["mongodb", "sqlite"])
def user_database_kind(request) -> str:
    return request.param


@pytest.mark.asyncio
@pytest.mark.manager
class TestGet:
    async def test_not_existing_user(self, user_manager: UserManagerMock[UserModel]):
        with pytest.raises(UserNotExists):
            await user_manager.get(generate_id())

    async def test_existing_user(
        self, user_manager: UserManagerMock[UserModel], user: UserModel
    ):
        retrieved_user = await user_manager.get(user.id)
        assert retrieved_user.id == user.id


@pytest.mark.asyncio
@pytest.mark.manager
class TestGetByEmail:
    async def test_not_existing_user(self, user_manager: UserManagerMock[UserModel]):
        with pytest.raises(UserNotExists):
            await user_manager.get_by_email("lancelot@camelot.bt")

    async def test_existing_user(
        self, user_manager: UserManagerMock[UserModel], user: UserModel
    ):
        retrieved_user = await user_manager.get_by_email(user.email)
        assert retrieved_user.id == user.id

    async def test_email_in_another_case(
        self, user_manager: UserManagerMock[UserModel], user: UserModel
    ):
        retrieved_user = await user_manager.get_by_email(user.email.upper())
        assert retrieved_user.id == user.id


@pytest.mark.asyncio
@pytest.mark.manager
class TestGetByOAuthAccount:
    async def test_not_existing_user(
        self, user_manager_oauth: UserManagerMock[UserModel]
    ):
        with pytest.raises(UserNotExists):
            await user_manager_oauth.get_by_oauth_account("service1", "foo")

    async def test_existing_user(
        self, user_manager_oauth: UserManagerMock[UserModel], user_oauth: UserOAuthModel
    ):
        oauth_account = user_oauth.oauth_accounts[0]
        retrieved_user = await user_manager_oauth.get_by_oauth_account(
            oauth_account.oauth_name, oauth_account.account_id
        )
        assert retrieved_user.id == user_oauth.id


@pytest.mark.asyncio
@pytest.mark.manager
class TestOAuthCallback:
    async def test_existing_user_with_oauth(
        self,
        user_manager_oauth: UserManagerMock[UserOAuthModel],
        user_oauth: UserOAuthModel,
    ):
        oauth_account = user_oauth.oauth_accounts[0]

        user = await user_manager_oauth.oauth_callback(
            oauth_account.oauth_name,
            "UPDATED_TOKEN",
            oauth_account.account_id,
            oauth_account.account_email,
        )

        assert user.id == user_oauth.id
        assert len(user.oauth_accounts) == 2
        assert user.oauth_accounts[0].id == oauth_account.id
        assert user.oauth_accounts[0].oauth_name == "service1"
        assert user.oauth_accounts[0].access_token == "UPDATED_TOKEN"
        assert user.oauth_accounts[1].access_token == "TOKEN"
        assert user.oauth_accounts[1].oauth_name == "service2"
        assert await user_manager_oauth.get(user.id) == user

        assert user_manager_oauth.on_after_register.called is False

    async def test_existing_user_without_oauth_associate(
        self,
        user_manager_oauth: UserManagerMock[UserOAuthModel],
        superuser_oauth: UserOAuthModel,
    ):
        user = await user_manager_oauth.oauth_callback(
            "service1",
            "TOKEN",
            "superuser_oauth1",
            superuser_oauth.email,
            1579000751,
            associate_by_email=True,
        )

        assert user.id == superuser_oauth.id
        assert len(user.oauth_accounts) == 1
        assert user.oauth_accounts[0].id is not None

        assert user_manager_oauth.on_after_register.called is False

    async def test_existing_user_without_oauth_no_associate(
        self,
        user_manager_oauth: UserManagerMock[UserOAuthModel],
        superuser_oauth: UserOAuthModel,
    ):
        with pytest.raises(UserAlreadyExists):
            await user_manager_oauth.oauth_callback(
                "service1",
                "TOKEN",
                "superuser_oauth1",
                superuser_oauth.email,
                1579000751,
                associate_by_email=False,
            )

    async def test_new_user(self, user_manager_oauth: UserManagerMock[UserOAuthModel]):
        user = await user_manager_oauth.oauth_callback(
            "service1", "TOKEN", "new_user_oauth1", "galahad@camelot.bt", 1579000751
        )

        assert user.email == "galahad@camelot.bt"
        assert len(user.oauth_accounts) == 1
        assert user.oauth_accounts[0].id is not None
        assert user.is_verified is False

        assert user_manager_oauth.on_after_register.called is True

    async def test_new_user_is_verified_by_default(
        self, user_manager_oauth: UserManagerMock[UserOAuthModel]
    ):
        user = await user_manager_oauth.oauth_callback(
            "service1",
            "TOKEN",
            "new_user_oauth1",
            "galahad@camelot.bt",
            1579000751,
            is_verified_by_default=True,
        )

        assert user.email == "galahad@camelot.bt"
        assert len(user.oauth_accounts) == 1
        assert user.oauth_accounts[0].id is not None
        assert user.is_verified is True

        assert user_manager_oauth.on_after_register.called is True


@pytest.fixture
def ruled_user_manager(user_database_oauth):
    rules = {
        "service1": ProviderRules(email_regex=r".*@camelot\.bt$", roles=("researcher",))
    }
    return UserManagerOAuth(user_database_oauth, UserOAuthModel, rules)


@pytest.mark.asyncio
@pytest.mark.manager
class TestProviderRules:
    async def test_new_user_gets_the_provider_roles(self, ruled_user_manager):
        user = await ruled_user_manager.oauth_callback(
            "service1", "TOKEN", "new_user_oauth1", "galahad@camelot.bt"
        )

        assert user.roles == {"researcher"}
        assert (await ruled_user_manager.get(user.id)).roles == {"researcher"}

    async def test_linked_user_gains_the_provider_roles(
        self, ruled_user_manager, superuser_oauth: UserOAuthModel
    ):
        user = await ruled_user_manager.oauth_callback(
            "service1",
            "TOKEN",
            "superuser_oauth1",
            superuser_oauth.email,
            associate_by_email=True,
        )

        assert user.roles == {"researcher", *superuser_oauth.roles}

    async def test_refreshed_account_grants_nothing_new(
        self, ruled_user_manager, user_oauth: UserOAuthModel
    ):
        account = user_oauth.oauth_accounts[0]
        user = await ruled_user_manager.oauth_callback(
            account.oauth_name,
            "UPDATED_TOKEN",
            account.account_id,
            account.account_email,
        )

        assert user.roles == user_oauth.roles

    async def test_email_off_the_pattern_is_not_permitted(self, ruled_user_manager):
        with pytest.raises(EmailNotPermitted):
            await ruled_user_manager.oauth_callback(
                "service1", "TOKEN", "new_user_oauth1", "mordred@orkney.bt"
            )

    async def test_provider_without_rules_is_unsupported(self, ruled_user_manager):
        with pytest.raises(UnsupportedProvider):
            await ruled_user_manager.oauth_callback(
                "service2", "TOKEN", "new_user_oauth1", "galahad@camelot.bt"
            )


@pytest.mark.asyncio
@pytest.mark.manager
async def test_on_after_login_runs_the_callback(user_database, user: UserModel):
    logged_in_users = []

    async def on_after_login(logged_in_user: UserModel) -> None:
        logged_in_users.append(logged_in_user)

    manager = UserManager(user_database, UserModel, on_after_login=on_after_login)
    await manager.on_after_login(user)

    assert logged_in_users == [user]
