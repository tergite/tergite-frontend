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
"""FastAPIUsers-specific definition of Authentication Backend"""
from typing import Optional

from fastapi import status
from fastapi.responses import Response
from fastapi_users.authentication import Transport
from fastapi_users.authentication.strategy import StrategyDestroyNotSupportedError
from fastapi_users.authentication.transport import TransportLogoutNotSupportedError
from fastapi_users.types import DependencyCallable

from .dtos import AppTokenCreate, AppTokenRead, AppTokenUpdate
from .strategy import AppTokenStrategy


class AppTokenAuthenticationBackend:
    """Combination of an authentication transport and strategy.

    Together, they provide a full authentication method logic.

    Attributes:
        name: Name of the backend.
        transport: Authentication transport instance.
        get_strategy: Dependency callable returning
            an authentication strategy instance.
    """

    name: str
    transport: Transport

    def __init__(
        self,
        name: str,
        transport: Transport,
        get_strategy: DependencyCallable[AppTokenStrategy],
    ):
        self.name = name
        self.transport = transport
        self.get_strategy = get_strategy

    async def generate_token(
        self,
        strategy: AppTokenStrategy,
        payload: AppTokenCreate,
        user_id: str,
        **kwargs,
    ) -> Response:
        """Generates a new token for the given user

        Args:
            strategy: the FastAPIUsers strategy to use
            payload: the payload for the creation of the app token
            user_id: the id of the user for whom the given token is to be created

        Returns:
            FastAPI response of the created token
        """
        token = await strategy.write_token(payload, user_id=user_id)
        return await self.transport.get_login_response(token)

    async def destroy_token(
        self,
        strategy: AppTokenStrategy,
        _id: str,
        user_id: str,
        **kwargs,
    ) -> Response:
        """Destroys a given token.

        Args:
            strategy: the FastAPIUsers strategy to use
            _id: the ID of the token to destroy
            user_id: the id of the user this token should belong to

        Raises:
            HTTPException: Forbidden 403 if token is not user's or token does not exist

        Returns:
            FastAPI response of the deleted token
        """
        try:
            await strategy.destroy_token(_id=_id, user_id=user_id)
        except StrategyDestroyNotSupportedError:
            pass

        try:
            response = await self.transport.get_logout_response()
        except TransportLogoutNotSupportedError:
            response = Response(status_code=status.HTTP_204_NO_CONTENT)

        return response

    async def update_token(
        self,
        strategy: AppTokenStrategy,
        _id: str,
        user_id: str,
        payload: AppTokenUpdate,
        **kwargs,
    ) -> Optional[AppTokenRead]:
        """Updates a given token.

        Returns None if the token is already expired, is non-existent or belongs to another user

        Args:
            strategy: the FastAPIUsers strategy to use
            _id: the ID of the token to update
            user_id: the id of the user this token should belong to
            payload: the update to add to the token

        Returns:
            the updated token or None if the token was expired, belonged to another user or did not exist
        """
        return await strategy.update_token(
            token_id=_id, user_id=user_id, payload=payload
        )
