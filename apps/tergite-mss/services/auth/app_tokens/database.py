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
from typing import Any, Dict, List, Mapping, Optional

from beanie import PydanticObjectId
from fastapi_users_db_beanie.access_token import BeanieAccessTokenDatabase

from . import exc
from .dtos import AppToken, AppTokenUpdate


class AppTokenDatabase(BeanieAccessTokenDatabase):
    """
    App token database adapter.
    """

    def __init__(self):
        super().__init__(AppToken)

    async def get_by_token(self, token: str, *args, **filters) -> Optional[AppToken]:
        """Gets an AppToken by the token

        Args:
            token: the token of the AppToken to get
            filters: any extra filters to match against apart from the token

        Returns:
            the matched AppToken or None if no document was matched
        """
        filters["token"] = token
        return await self._find_one(filters)

    async def get(self, _id: PydanticObjectId, *args, **filters) -> Optional[AppToken]:
        """Gets an AppToken by _id

        Args:
            _id: the ID of the AppToken to get
            filters: any extra filters to match against apart from the _id

        Returns:
            the matched AppToken or None if no document was matched
        """
        filters["_id"] = _id
        return await self._find_one(filters)

    async def update(
        self,
        _id: PydanticObjectId,
        payload: AppTokenUpdate,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[AppToken]:
        """Updates an AppToken of _id, and given filters, with the given payload

        Args:
            _id: the ID of the AppToken to get
            filters: any extra filters to match against apart from the _id
            payload: the AppTokenUpdate instance to use to update the token

        Returns:
            the matched AppToken or None if no document was matched
        """
        if filters is None:
            filters = {}

        filters["_id"] = _id
        token: Optional[AppToken] = await self._find_one(filters)
        if isinstance(token, AppToken):
            new_lifespan_seconds = (
                payload.expires_at - token.created_at
            ).total_seconds()
            return await token.set({"lifespan_seconds": new_lifespan_seconds})

        return token

    async def _find_one(self, _filter) -> Optional[AppToken]:
        """Finds the given token by the given filter.

        It deletes expired tokens automatically

        Args:
            _filter: the filter object to match against

        Returns:
            the matched AppToken or None if no document was matched
        """
        token: Optional[AppToken] = await self.access_token_model.find_one(_filter)
        if _is_token_expired(token):
            # return None for tokens that are past their age
            # delete expired tokens automatically
            await token.delete()
            return None

        return token

    @staticmethod
    async def delete_many(
        filter_obj: Mapping[str, Any], skip: int = 0, limit: Optional[int] = None
    ) -> None:
        """
        Deletes a list of tokens to basing on filter.

        Args:
            filter_obj: the PyMongo-like filter object e.g. `{"user_id": "uidufiud"}`.
            skip: the number of matched records to skip
            limit: the maximum number of records to return.
                If None, all possible records are returned.

        Returns:
            the list of matched tokens
        """
        return await AppToken.find(
            filter_obj,
            skip=skip,
            limit=limit,
        ).delete()

    @staticmethod
    async def delete_one(filters: Mapping[str, Any]) -> None:
        """
        Deleted the first token to match the given filter.

        Args:
            filters: the PyMongo-like filter object e.g. `{"user_id": "uidufiud"}`.

        Returns:
            the deleted token

        Raises:
            exc.AppTokenNotFound: app token does not exist.
        """
        result = await AppToken.find_one(filters).delete()
        if result.deleted_count == 0:
            raise exc.AppTokenNotFound("app token does not exist.")

    @staticmethod
    async def get_many(
        filter_obj: Mapping[str, Any], skip: int = 0, limit: Optional[int] = None
    ) -> List[AppToken]:
        """
        Get a list of app tokens basing on filter.

        Args:
            filter_obj: the PyMongo-like filter object e.g. `{"user_id": "uidufiud"}`.
            skip: the number of matched records to skip
            limit: the maximum number of records to return.
                If None, all possible records are returned.

        Returns:
            the list of matched projects
        """
        return await AppToken.find(
            filter_obj,
            skip=skip,
            limit=limit,
        ).to_list()


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
