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
"""Users and their OAuth accounts, kept in the Database the app gives authlib

The app's user schema is a storage Schema whose `email` is listed in `case_insensitive`, as
users are found by email whatever its case. An OAuth user's schema holds
`oauth_accounts: List[<account model>]` in `indexed_lists`, which is set whole on each change.
"""
import re
from typing import Any, Dict, List, Optional, Set, Type, get_args

from libs.storage import Database

from . import models
from .errors import EmailNotPermitted, UserAlreadyExists
from .providers import OAuthProvider


async def sign_in_with_oauth(
    database: Database,
    user_schema: Type[models.UOAP],
    provider_name: str,
    provider: OAuthProvider,
    account: Dict[str, Any],
) -> models.UOAP:
    """Gets the user an OAuth account signs in, linking or creating them as the rule says

    The user who has the account gets its new token. Otherwise a user of its email has it
    linked, if the provider links by email; otherwise a user is created with it. Linking
    or creating grants the provider's roles.

    Args:
        database: the database where the users are kept
        user_schema: the storage schema of the users
        provider_name: the name of the provider, as the account records it
        provider: the provider signed in with
        account: the account's values: account_id, account_email, access_token,
            expires_at and refresh_token

    Raises:
        EmailNotPermitted: the email does not match the provider's email_regex
        UserAlreadyExists: a user has the email, and the provider does not link by email
    """
    email = account["account_email"]
    if re.match(provider.email_regex, email) is None:
        raise EmailNotPermitted()
    account = {**account, "oauth_name": provider_name}
    roles = set(provider.roles)

    user = await get_user_by_oauth_account(
        database, user_schema, provider_name, account["account_id"]
    )
    if user is not None:
        return await update_oauth_account(
            database, user, provider_name, account["account_id"], account
        )

    user = await get_user_by_email(database, user_schema, email)
    if user is not None and not provider.should_associate_by_email:
        raise UserAlreadyExists()
    if user is not None:
        return await add_oauth_account(database, user, account, roles=roles)

    return await create_oauth_user(
        database,
        user_schema,
        email=email,
        is_verified=provider.is_verified_by_default,
        account=account,
        roles=roles,
    )


async def get_user(
    database: Database, user_schema: Type[models.UP], user_id: str
) -> Optional[models.UP]:
    return await database.get(user_schema, user_id)


async def get_user_by_oauth_account(
    database: Database, user_schema: Type[models.UOAP], oauth_name: str, account_id: str
) -> Optional[models.UOAP]:
    account_filter = {"oauth_name": oauth_name, "account_id": account_id}
    return await database.find_one(
        user_schema, {"oauth_accounts": {"$elemMatch": account_filter}}
    )


async def get_user_by_email(
    database: Database, user_schema: Type[models.UP], email: str
) -> Optional[models.UP]:
    return await database.find_one(user_schema, {"email": email})


async def update_oauth_account(
    database: Database,
    user: models.UOAP,
    oauth_name: str,
    account_id: str,
    values: Dict[str, Any],
) -> models.UOAP:
    """Replaces the values of the user's account with that provider and account id"""
    accounts = []
    for account in _get_account_values(user):
        if account["oauth_name"] == oauth_name and account["account_id"] == account_id:
            account = {**account, **values}
        accounts.append(account)
    return await database.update_one(
        type(user),
        {"id": user.id},
        {"$set": {"oauth_accounts": _get_validated_accounts(user, accounts)}},
    )


async def add_oauth_account(
    database: Database, user: models.UOAP, account: Dict[str, Any], roles: Set[str]
) -> models.UOAP:
    """Links an OAuth account to the user, who gains the roles it grants"""
    accounts = _get_validated_accounts(user, [*_get_account_values(user), account])
    return await database.update_one(
        type(user),
        {"id": user.id},
        {"$set": {"oauth_accounts": accounts, "roles": list(user.roles | roles)}},
    )


async def create_oauth_user(
    database: Database,
    user_schema: Type[models.UOAP],
    email: str,
    is_verified: bool,
    account: Dict[str, Any],
    roles: Set[str],
) -> models.UOAP:
    """Creates a user with its first OAuth account, in one write

    The user has the roles the schema gives every new user, and those the account grants.
    """
    user = user_schema(email=email, is_verified=is_verified, oauth_accounts=[account])
    user = user.model_copy(update={"roles": user.roles | roles})
    return await database.insert(user_schema, user)


def _get_account_values(user: models.UOAP) -> List[Dict[str, Any]]:
    return [account.model_dump() for account in user.oauth_accounts]


def _get_validated_accounts(
    user: models.UOAP, accounts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Gets the accounts as the user's schema keeps them, so that a new one gets its id"""
    (account_model,) = get_args(type(user).model_fields["oauth_accounts"].annotation)
    return [account_model.model_validate(account).model_dump() for account in accounts]
