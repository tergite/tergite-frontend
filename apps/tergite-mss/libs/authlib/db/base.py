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
from typing import Any, Generic, Optional

from libs.authlib.models import ID, OAP, UOAP, UP
from libs.authlib.types import DependencyCallable


class BaseUserDatabase(Generic[UP, ID]):
    """Base adapter for retrieving, creating and updating users from a database."""

    async def get(self, id: ID) -> Optional[UP]:
        """Get a single user by id."""
        raise NotImplementedError()

    async def get_by_email(self, email: str) -> Optional[UP]:
        """Get a single user by email."""
        raise NotImplementedError()

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> Optional[UP]:
        """Get a single user by OAuth account id."""
        raise NotImplementedError()

    async def create(self, create_dict: dict[str, Any]) -> UP:
        """Create a user."""
        raise NotImplementedError()

    async def update(self, user: UP, update_dict: dict[str, Any]) -> UP:
        """Update a user."""
        raise NotImplementedError()

    async def delete(self, user: UP) -> None:
        """Delete a user."""
        raise NotImplementedError()

    async def add_oauth_account(
        self: "BaseUserDatabase[UOAP, ID]", user: UOAP, create_dict: dict[str, Any]
    ) -> UOAP:
        """Create an OAuth account and add it to the user."""
        raise NotImplementedError()

    async def update_oauth_account(
        self: "BaseUserDatabase[UOAP, ID]",
        user: UOAP,
        oauth_account: OAP,
        update_dict: dict[str, Any],
    ) -> UOAP:
        """Update an OAuth account on a user."""
        raise NotImplementedError()


UserDatabaseDependency = DependencyCallable[BaseUserDatabase[UP, ID]]
