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

"""Definition of the FastAPIUsers-specific Database adapter for app tokens"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from libs.storage import Database, Filter

from . import exc
from .dtos import AppToken, AppTokenUpdate


class AppTokenDatabase:
    """
    App token database adapter.
    """

    def __init__(self, database: Database):
        self.database = database

    async def create(self, token: AppToken) -> AppToken:
        return await self.database.insert(AppToken, token)

    async def get_by_token(self, token: str) -> Optional[AppToken]:
        """Gets an AppToken by the token, or None if there is none or it has expired"""
        return await self._find_one({"token": token})

    async def update(
        self, _id: str, user_id: str, payload: AppTokenUpdate
    ) -> Optional[AppToken]:
        """Updates the user's AppToken of _id with the given payload

        Args:
            _id: the ID of the AppToken to update
            user_id: the ID of the user the AppToken must belong to
            payload: the AppTokenUpdate instance to use to update the token

        Returns:
            the updated AppToken or None if no unexpired token was matched
        """
        token = await self._find_one({"id": _id, "user_id": user_id})
        if token is None:
            return None

        new_lifespan_seconds = (payload.expires_at - token.created_at).total_seconds()
        return await self.database.update_one(
            AppToken,
            {"id": token.id},
            {"$set": {"lifespan_seconds": new_lifespan_seconds}},
        )

    async def delete_many(self, token_filter: Filter) -> int:
        """Deletes the matched tokens, returning how many were deleted"""
        return await self.database.delete_many(AppToken, token_filter)

    async def delete_one(self, token_filter: Filter) -> None:
        """Deletes the first token to match the given filter.

        Raises:
            exc.AppTokenNotFound: app token does not exist.
        """
        if await self.database.delete_one(AppToken, token_filter) is None:
            raise exc.AppTokenNotFound("app token does not exist.")

    async def get_many(
        self, token_filter: Filter, skip: int = 0, limit: Optional[int] = None
    ) -> List[AppToken]:
        """Gets the app tokens that match the filter"""
        return await self.database.find(
            AppToken, filter=token_filter, skip=skip, limit=limit
        )

    async def _find_one(self, token_filter: Filter) -> Optional[AppToken]:
        """Finds the first token to match the filter, deleting it instead if expired"""
        token = await self.database.find_one(AppToken, token_filter)
        if _is_token_expired(token):
            await self.database.delete_one(AppToken, {"id": token.id})
            return None

        return token


def _is_token_expired(token: Optional[AppToken]) -> bool:
    """Checks whether the token is expired or not

    Args:
        token: the app token to be checked

    Returns:
        True if token is expired or False
    """
    try:
        lifespan = datetime.now(timezone.utc) - token.created_at
        return lifespan >= timedelta(seconds=token.lifespan_seconds)
    except AttributeError:
        return False
