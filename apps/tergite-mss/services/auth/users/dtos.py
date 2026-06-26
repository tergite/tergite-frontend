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

"""Data Transafer Objects for the users submodule of the auth service"""
from typing import List, Set, TypeVar

from beanie import Document, PydanticObjectId
from fastapi_users import schemas
from fastapi_users.types import DependencyCallable
from fastapi_users_db_beanie import BaseOAuthAccount
from pydantic import Field, field_serializer
from pymongo import IndexModel
from pymongo.collation import Collation

from utils.config import UserRole

USER_DB_COLLECTION = "auth_users"


class UserRead(schemas.BaseUser[PydanticObjectId]):
    roles: Set[UserRole] = {}

    @field_serializer("id", when_used="json")
    def serialize_id(self, _id: PydanticObjectId):
        """Convert id to string when working with JSON"""
        return str(_id)


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


class OAuthAccount(BaseOAuthAccount):
    pass


class User(Document):
    email: str
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False
    oauth_accounts: List[OAuthAccount] = Field(default_factory=list)
    roles: Set[UserRole] = {UserRole.USER}

    class Settings:
        name = USER_DB_COLLECTION
        email_collation = Collation("en", strength=2)
        indexes = [
            IndexModel("email", unique=True),
            IndexModel(
                "email", name="case_insensitive_email_index", collation=email_collation
            ),
        ]

    @property
    def is_superuser(self):
        return UserRole.ADMIN in self.roles

    @is_superuser.setter
    def is_superuser(self, value: bool):
        if value:
            self.roles.add(UserRole.ADMIN)
        elif not value:
            try:
                self.roles.remove(UserRole.ADMIN)
            except KeyError:
                pass

    @property
    def username(self):
        return self.email.split("@")[0]


CurrentUserDependency = DependencyCallable[User]
CurrentSuperUserDependency = DependencyCallable[User]
CurrentUserIdDependency = DependencyCallable[str]
UP = TypeVar("UP", bound=User)
ID = TypeVar("ID")
