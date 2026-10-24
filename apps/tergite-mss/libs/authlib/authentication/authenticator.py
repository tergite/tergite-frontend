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
"""Dependencies that get the user of a request's session token"""
from collections.abc import Sequence
from typing import Awaitable, Callable, Generic, List, Optional, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer

from libs.authlib import models
from libs.authlib.authentication.strategy import Strategy
from libs.authlib.manager import BaseUserManager, UserManagerDependency
from libs.authlib.types import DependencyCallable


class Authenticator(Generic[models.UP, models.ID]):
    """
    Provides dependency callables to retrieve authenticated user.

    The session token is read from the `Authorization: Bearer` header, then from the
    session cookie, if one is named: the first that the strategy reads into a user wins.
    If none does, an HTTPException is raised.

    :param get_user_manager: User manager dependency callable.
    :param get_strategy: Dependency callable of the strategy that reads tokens.
    :param cookie_name: The name of the session cookie; None reads no cookie.
    """

    def __init__(
        self,
        get_user_manager: UserManagerDependency[models.UP, models.ID],
        get_strategy: DependencyCallable[Strategy[models.UP, models.ID]],
        cookie_name: Optional[str] = None,
    ):
        self.get_user_manager = get_user_manager
        self.get_strategy = get_strategy
        self.bearer_scheme = HTTPBearer(auto_error=False)
        self.cookie_scheme = (
            APIKeyCookie(name=cookie_name, auto_error=False)
            if cookie_name is not None
            else _read_no_cookie
        )

    def current_user_token(
        self,
        optional: bool = False,
        active: bool = False,
        verified: bool = False,
        superuser: bool = False,
    ):
        """
        Return a dependency callable to retrieve currently authenticated user and token.

        :param optional: If `True`, `None` is returned if there is no authenticated user
        or if it doesn't pass the other requirements.
        Otherwise, throw `401 Unauthorized`. Defaults to `False`.
        :param active: If `True`, throw `401 Unauthorized` if
        the authenticated user is inactive. Defaults to `False`.
        :param verified: If `True`, throw `403 Forbidden` if
        the authenticated user is not verified. Defaults to `False`.
        :param superuser: If `True`, throw `403 Forbidden` if
        the authenticated user is not a superuser. Defaults to `False`.
        """

        async def current_user_token_dependency(
            bearer: Optional[HTTPAuthorizationCredentials] = Depends(
                self.bearer_scheme
            ),
            cookie_token: Optional[str] = Depends(self.cookie_scheme),
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(
                self.get_user_manager
            ),
            strategy: Strategy[models.UP, models.ID] = Depends(self.get_strategy),
        ):
            return await self._authenticate(
                _get_tokens(bearer, cookie_token),
                user_manager,
                strategy,
                optional=optional,
                active=active,
                verified=verified,
                superuser=superuser,
            )

        return current_user_token_dependency

    def current_user(
        self,
        optional: bool = False,
        active: bool = False,
        verified: bool = False,
        superuser: bool = False,
        roles: Sequence[str] = (),
    ):
        """
        Return a dependency callable to retrieve currently authenticated user.

        :param optional: If `True`, `None` is returned if there is no authenticated user
        or if it doesn't pass the other requirements.
        Otherwise, throw `401 Unauthorized`. Defaults to `False`.
        :param active: If `True`, throw `401 Unauthorized` if
        the authenticated user is inactive. Defaults to `False`.
        :param verified: If `True`, throw `403 Forbidden` if
        the authenticated user is not verified. Defaults to `False`.
        :param superuser: If `True`, throw `403 Forbidden` if
        the authenticated user is not a superuser. Defaults to `False`.
        :param roles: The roles of which the user must have one, or throw
        `403 Forbidden`. Defaults to none required.
        """
        get_current_user_token = self.current_user_token(
            optional=optional, active=active, verified=verified, superuser=superuser
        )

        async def current_user_dependency(
            user_token: Tuple[Optional[models.UP], Optional[str]] = Depends(
                get_current_user_token
            ),
        ):
            user, _ = user_token
            if user and roles and user.roles.isdisjoint(roles):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
            return user

        return current_user_dependency

    def get_current_user_id(
        self, is_optional: bool = False
    ) -> Callable[..., Awaitable[Optional[str]]]:
        """
        Return a dependency callable to retrieve the authenticated user's id.

        It reads the id from the token alone, never the database, so it does not know
        whether the user is still active.

        :param is_optional: If `True`, `None` is returned if there is no authenticated
        user. Otherwise, throw `401 Unauthorized`. Defaults to `False`.
        """

        async def read_current_user_id(
            bearer: Optional[HTTPAuthorizationCredentials] = Depends(
                self.bearer_scheme
            ),
            cookie_token: Optional[str] = Depends(self.cookie_scheme),
            strategy: Strategy[models.UP, models.ID] = Depends(self.get_strategy),
        ) -> Optional[str]:
            for token in _get_tokens(bearer, cookie_token):
                user_id = strategy.get_user_id(token)
                if user_id:
                    return user_id
            if not is_optional:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
            return None

        return read_current_user_id

    async def _authenticate(
        self,
        tokens: List[str],
        user_manager: BaseUserManager[models.UP, models.ID],
        strategy: Strategy[models.UP, models.ID],
        optional: bool = False,
        active: bool = False,
        verified: bool = False,
        superuser: bool = False,
    ) -> tuple[Optional[models.UP], Optional[str]]:
        user: Optional[models.UP] = None
        token: Optional[str] = None
        for token in tokens:
            user = await strategy.read_token(token, user_manager)
            if user:
                break

        status_code = status.HTTP_401_UNAUTHORIZED
        if user:
            status_code = status.HTTP_403_FORBIDDEN
            if active and not user.is_active:
                status_code = status.HTTP_401_UNAUTHORIZED
                user = None
            elif (
                verified and not user.is_verified or superuser and not user.is_superuser
            ):
                user = None
        if not user and not optional:
            raise HTTPException(status_code=status_code)
        return user, token


def _get_tokens(
    bearer: Optional[HTTPAuthorizationCredentials], cookie_token: Optional[str]
) -> List[str]:
    """Gets the request's tokens, the bearer's first"""
    tokens = []
    if bearer is not None:
        tokens.append(bearer.credentials)
    if cookie_token is not None:
        tokens.append(cookie_token)
    return tokens


async def _read_no_cookie() -> None:
    return None
