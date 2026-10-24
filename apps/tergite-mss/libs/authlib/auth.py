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
"""An app's configured auth, and the dependencies that get a request's user"""
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
)

from fastapi import Depends
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer

from libs.storage import Database, is_id

from . import models, users
from .cookies import SessionCookie
from .errors import Forbidden, Unauthorized
from .providers import OAuthProvider
from .tokens import SecretType, read_session_user_id

UserDependency = Callable[..., Awaitable[Any]]


class Auth(Generic[models.UOAP]):
    """The auth of an app: where its users are kept, who signs them in, and their sessions

    A session token is read from the `Authorization: Bearer` header, then from the
    session cookie: the first naming a user wins.

    Args:
        database: the database where the users are kept
        user_schema: the storage schema of the users
        providers: the OAuth providers users sign in with, by name
        secret: the secret that signs session and state tokens
        session_lifetime_seconds: how long a session token lasts; None for ever
        cookie: the session cookie
        on_after_login: what the app does with each user who logs in, if anything
    """

    def __init__(
        self,
        database: Database,
        user_schema: Type[models.UOAP],
        providers: Mapping[str, OAuthProvider],
        secret: SecretType,
        session_lifetime_seconds: Optional[int],
        cookie: SessionCookie,
        on_after_login: Optional[Callable[[models.UOAP], Awaitable[Any]]] = None,
    ):
        self.database = database
        self.user_schema = user_schema
        self.providers = providers
        self.secret = secret
        self.session_lifetime_seconds = session_lifetime_seconds
        self.cookie = cookie
        self.on_after_login = on_after_login
        self._bearer_scheme = HTTPBearer(auto_error=False)
        self._cookie_scheme = APIKeyCookie(name=cookie.name, auto_error=False)

    def get_current_user(
        self,
        is_optional: bool = False,
        should_require_active: bool = False,
        should_require_verified: bool = False,
        should_require_superuser: bool = False,
        roles: Sequence[str] = (),
    ) -> UserDependency:
        """Gets a dependency that gives the request's user

        Args:
            is_optional: whether to give None instead of refusing the request
            should_require_active: whether an inactive user is refused, with a 401
            should_require_verified: whether an unverified user is refused, with a 403
            should_require_superuser: whether a user who is not a superuser is refused,
                with a 403
            roles: the roles of which the user must have one, or be refused with a 403;
                none required if empty
        """

        async def read_current_user(
            bearer: Optional[HTTPAuthorizationCredentials] = Depends(
                self._bearer_scheme
            ),
            cookie_token: Optional[str] = Depends(self._cookie_scheme),
        ) -> Optional[models.UOAP]:
            user = await self._find_session_user(_get_tokens(bearer, cookie_token))
            if user is None or (should_require_active and not user.is_active):
                return _reject(Unauthorized(), is_optional)
            if should_require_verified and not user.is_verified:
                return _reject(Forbidden(), is_optional)
            if should_require_superuser and not user.is_superuser:
                return _reject(Forbidden(), is_optional)
            if roles and user.roles.isdisjoint(roles):
                return _reject(Forbidden(), is_optional)
            return user

        return read_current_user

    def get_current_user_id(self, is_optional: bool = False) -> UserDependency:
        """Gets a dependency that gives the id of the request's user, from the token alone

        It never reads the database, so it does not know whether the user is still active.

        Args:
            is_optional: whether to give None instead of refusing the request with a 401
        """

        async def read_current_user_id(
            bearer: Optional[HTTPAuthorizationCredentials] = Depends(
                self._bearer_scheme
            ),
            cookie_token: Optional[str] = Depends(self._cookie_scheme),
        ) -> Optional[str]:
            for token in _get_tokens(bearer, cookie_token):
                user_id = read_session_user_id(token, self.secret)
                if user_id is not None:
                    return user_id
            return _reject(Unauthorized(), is_optional)

        return read_current_user_id

    async def _find_session_user(self, tokens: List[str]) -> Optional[models.UOAP]:
        """Finds the user of the first token that names one who exists"""
        for token in tokens:
            user_id = read_session_user_id(token, self.secret)
            if user_id is None or not is_id(user_id):
                continue
            user = await users.get_user(self.database, self.user_schema, user_id)
            if user is not None:
                return user
        return None


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


def _reject(error: Exception, is_optional: bool) -> None:
    """Rejects the request with the error, or gives None if the user is optional"""
    if not is_optional:
        raise error
    return None
