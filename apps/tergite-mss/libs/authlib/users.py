# This code is part of Tergite
#
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
from typing import Any, Dict, List, Optional, Set, Type, get_args

from libs.storage import Database

from . import models


async def get_user(
    database: Database, user_schema: Type[models.UP], user_id: str
) -> Optional[models.UP]:
    return await database.get(user_schema, user_id)


async def get_user_by_email(
    database: Database, user_schema: Type[models.UP], email: str
) -> Optional[models.UP]:
    return await database.find_one(user_schema, {"email": email})


async def get_user_by_oauth_account(
    database: Database, user_schema: Type[models.UOAP], oauth_name: str, account_id: str
) -> Optional[models.UOAP]:
    account_filter = {"oauth_name": oauth_name, "account_id": account_id}
    return await database.find_one(
        user_schema, {"oauth_accounts": {"$elemMatch": account_filter}}
    )


async def create_oauth_user(
    database: Database,
    user_schema: Type[models.UOAP],
    email: str,
    is_verified: bool,
    account: Dict[str, Any],
    roles: Set[str],
) -> models.UOAP:
    """Creates a user with its first OAuth account and the roles it grants, in one write"""
    user = user_schema(
        email=email,
        is_verified=is_verified,
        roles=roles,
        oauth_accounts=[account],
    )
    return await database.insert(user_schema, user)


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


def _get_account_values(user: models.UOAP) -> List[Dict[str, Any]]:
    return [account.model_dump() for account in user.oauth_accounts]


def _get_validated_accounts(
    user: models.UOAP, accounts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Gets the accounts as the user's schema keeps them, so that a new one gets its id"""
    (account_model,) = get_args(type(user).model_fields["oauth_accounts"].annotation)
    return [account_model.model_validate(account).model_dump() for account in accounts]
