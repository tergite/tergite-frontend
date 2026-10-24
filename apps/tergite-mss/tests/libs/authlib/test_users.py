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
"""The users and the account-linking rule, on each database"""
import dataclasses

import pytest

from libs.authlib import EmailNotPermitted, UserAlreadyExists
from libs.authlib.users import get_user, get_user_by_email, sign_in_with_oauth
from tests.libs.authlib.conftest import UserModel


@pytest.fixture(params=["mongodb", "sqlite"])
def user_database_kind(request) -> str:
    return request.param


async def test_the_account_of_a_user_signs_them_in_with_its_new_token(
    user_database, provider, user
):
    signed_in = await sign_in_with_oauth(
        user_database,
        UserModel,
        "service1",
        provider,
        _get_account_values("user_oauth1", user.email, access_token="NEW_TOKEN"),
    )

    (account,) = signed_in.oauth_accounts
    assert signed_in.id == user.id
    assert account.id == user.oauth_accounts[0].id
    assert account.access_token == "NEW_TOKEN"
    assert await get_user(user_database, UserModel, user.id) == signed_in


async def test_a_user_of_the_email_is_refused_unless_the_provider_links_by_email(
    user_database, provider, superuser
):
    account = _get_account_values("merlin_oauth1", superuser.email)

    with pytest.raises(UserAlreadyExists):
        await sign_in_with_oauth(
            user_database, UserModel, "service1", provider, account
        )


async def test_a_user_of_the_email_is_linked_and_gains_the_provider_roles(
    user_database, provider, superuser
):
    linking_provider = dataclasses.replace(provider, should_associate_by_email=True)

    signed_in = await sign_in_with_oauth(
        user_database,
        UserModel,
        "service1",
        linking_provider,
        _get_account_values("merlin_oauth1", superuser.email),
    )

    assert signed_in.id == superuser.id
    assert [account.account_id for account in signed_in.oauth_accounts] == [
        "merlin_oauth1"
    ]
    assert signed_in.roles == {"admin", "researcher"}


@pytest.mark.parametrize("is_verified_by_default", [True, False])
async def test_a_new_email_creates_a_user_with_the_provider_roles(
    user_database, provider, is_verified_by_default
):
    creating_provider = dataclasses.replace(
        provider, is_verified_by_default=is_verified_by_default
    )

    signed_in = await sign_in_with_oauth(
        user_database,
        UserModel,
        "service1",
        creating_provider,
        _get_account_values("galahad_oauth1", "galahad@camelot.bt"),
    )

    assert signed_in.email == "galahad@camelot.bt"
    assert signed_in.is_verified is is_verified_by_default
    assert signed_in.roles == {"researcher"}
    assert signed_in.oauth_accounts[0].oauth_name == "service1"


async def test_an_email_off_the_provider_pattern_is_not_permitted(
    user_database, provider
):
    account = _get_account_values("mordred_oauth1", "mordred@orkney.bt")

    with pytest.raises(EmailNotPermitted):
        await sign_in_with_oauth(
            user_database, UserModel, "service1", provider, account
        )


async def test_a_user_is_found_by_email_in_any_case(user_database, user):
    found = await get_user_by_email(user_database, UserModel, user.email.upper())

    assert found.id == user.id


def _get_account_values(account_id: str, email: str, access_token: str = "TOKEN"):
    return {
        "access_token": access_token,
        "account_id": account_id,
        "account_email": email,
        "expires_at": None,
        "refresh_token": None,
    }
