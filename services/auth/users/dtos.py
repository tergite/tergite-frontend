# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""The users: who they are, the roles they hold, and the OAuth accounts they sign in with"""

from typing import List, Optional, Set

from pydantic import Field

from libs.authlib import BaseOAuthAccount, BaseUser
from libs.storage import Id, Schema, StorageSpec, generate_id
from utils.config import UserRole


class Role(Schema):
    """A role users may hold, kept so that a user's roles reference one"""

    __storage__ = StorageSpec(table="auth_roles", key="name")

    name: UserRole


class OAuthAccount(BaseOAuthAccount):
    """An OAuth account of a user, with the seven fields auth_users documents keep"""


class User(Schema):
    """A user, field for field as the auth_users documents written before step 7"""

    __storage__ = StorageSpec(
        table="auth_users",
        unique=("email",),
        case_insensitive=("email",),
        references={"roles": Role},
        indexed_lists=("oauth_accounts",),
        indexes=(("oauth_accounts.oauth_name", "oauth_accounts.account_id"),),
    )

    id: Id = Field(default_factory=generate_id)
    email: str
    # users signed in with fastapi-users carry a random one; none is needed since
    hashed_password: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    oauth_accounts: List[OAuthAccount] = Field(default_factory=list)
    roles: Set[UserRole] = {UserRole.USER}

    @property
    def is_superuser(self) -> bool:
        """Whether the user holds the admin role"""
        return UserRole.ADMIN in self.roles

    @property
    def username(self) -> str:
        """The part of the user's email before the '@'"""
        return self.email.split("@")[0]


class UserRead(BaseUser):
    """A user as shown to the user"""

    roles: Set[UserRole] = set()
