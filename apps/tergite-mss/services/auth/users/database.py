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

"""Definition of the FastAPIUsers-specific Database adapter for users"""
from typing import Any, Dict, List, Mapping, Optional, Sequence

from fastapi_users_db_beanie import BeanieUserDatabase

from utils.config import UserRole

from ..users.dtos import OAuthAccount, User


class UserDatabase(BeanieUserDatabase):
    def __init__(self, user_roles_config: Dict[str, Optional[Sequence[str]]] = None):
        super().__init__(
            user_model=User,
            oauth_account_model=OAuthAccount,
        )
        self.__roles_map = user_roles_config if user_roles_config else {}

    async def add_oauth_account(self, user: User, create_dict: Dict[str, Any]) -> User:
        try:
            oauth_name = create_dict["oauth_name"]
            user_roles = self.__roles_map[oauth_name]
            user.roles.update({UserRole(v) for v in user_roles if v})
        except (KeyError, TypeError):
            pass

        return await super().add_oauth_account(user, create_dict)

    @staticmethod
    async def get_many(
        filter_obj: Mapping[str, Any],
        skip: int = 0,
        limit: Optional[int] = None,
        **kwargs,
    ) -> List[User]:
        """
        Get a list of users basing on filter.

        Args:
            filter_obj: the PyMongo-like filter object e.g. `{"email": "john@example.com"}`.
            skip: the number of matched records to skip
            limit: the maximum number of records to return.
                If None, all possible records are returned.
            kwargs: Additional pymongo find() arguments.

        Returns:
            the list of matched users
        """
        return await User.find(
            filter_obj,
            skip=skip,
            limit=limit,
            **kwargs,
        ).to_list()
