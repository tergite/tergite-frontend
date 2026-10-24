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
import re
from typing import Any, Awaitable, Callable, Generic, Mapping, Optional, Set, Type

from fastapi import Request, Response

from libs.authlib import exceptions, models, users
from libs.authlib.providers import OAuthProvider
from libs.authlib.types import DependencyCallable
from libs.storage import Database, is_id


class BaseUserManager(Generic[models.UP, models.ID]):
    """
    User management logic.

    :param database: The database the users are kept in.
    :param user_schema: The storage schema of the users.
    :param providers: The OAuth providers whose sign-ins are taken, by name; None takes
    every provider's, granting no roles.
    :param on_after_login: What the app does with each user who logs in, if anything.
    """

    database: Database
    user_schema: Type[models.UP]
    providers: Optional[Mapping[str, OAuthProvider]]

    def __init__(
        self,
        database: Database,
        user_schema: Type[models.UP],
        providers: Optional[Mapping[str, OAuthProvider]] = None,
        on_after_login: Optional[Callable[[models.UP], Awaitable[Any]]] = None,
    ):
        self.database = database
        self.user_schema = user_schema
        self.providers = providers
        self._on_after_login = on_after_login

    def parse_id(self, value: Any) -> models.ID:
        """
        Parse a value into a user id, a storage Id.

        :param value: The value to parse.
        :raises InvalidID: The value is not an Id.
        :return: The id.
        """
        if not is_id(value):
            raise exceptions.InvalidID()
        return value

    async def get(self, id: models.ID) -> models.UP:
        """
        Get a user by id.

        :param id: Id. of the user to retrieve.
        :raises UserNotExists: The user does not exist.
        :return: A user.
        """
        user = await users.get_user(self.database, self.user_schema, id)

        if user is None:
            raise exceptions.UserNotExists()

        return user

    async def get_by_email(self, user_email: str) -> models.UP:
        """
        Get a user by e-mail.

        :param user_email: E-mail of the user to retrieve.
        :raises UserNotExists: The user does not exist.
        :return: A user.
        """
        user = await users.get_user_by_email(
            self.database, self.user_schema, user_email
        )

        if user is None:
            raise exceptions.UserNotExists()

        return user

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> models.UP:
        """
        Get a user by OAuth account.

        :param oauth: Name of the OAuth client.
        :param account_id: Id. of the account on the external OAuth service.
        :raises UserNotExists: The user does not exist.
        :return: A user.
        """
        user = await users.get_user_by_oauth_account(
            self.database, self.user_schema, oauth, account_id
        )

        if user is None:
            raise exceptions.UserNotExists()

        return user

    async def oauth_callback(
        self: "BaseUserManager[models.UOAP, models.ID]",
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: Optional[int] = None,
        refresh_token: Optional[str] = None,
        request: Optional[Request] = None,
        *,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
    ) -> models.UOAP:
        """
        Handle the callback after a successful OAuth authentication.

        If the user already exists with this OAuth account, the token is updated.

        If a user with the same e-mail already exists and `associate_by_email` is True,
        the OAuth account is associated to this user.
        Otherwise, the `UserNotExists` exception is raised.

        If the user does not exist, it is created and the on_after_register handler
        is triggered.

        :param oauth_name: Name of the OAuth client.
        :param access_token: Valid access token for the service provider.
        :param account_id: models.ID of the user on the service provider.
        :param account_email: E-mail of the user on the service provider.
        :param expires_at: Optional timestamp at which the access token expires.
        :param refresh_token: Optional refresh token to get a
        fresh access token from the service provider.
        :param request: Optional FastAPI request that
        triggered the operation, defaults to None
        :param associate_by_email: If True, any existing user with the same
        e-mail address will be associated to this user. Defaults to False.
        :param is_verified_by_default: If True, the `is_verified` flag will be
        set to `True` on newly created user. Make sure the OAuth Provider you're
        using does verify the email address before enabling this flag.
        Defaults to False.
        :raises UnsupportedProvider: The provider has no rules.
        :raises EmailNotPermitted: The email does not match the provider's email_regex.
        :return: A user.
        """
        roles = self._get_permitted_roles(oauth_name, account_email)
        oauth_account_dict = {
            "oauth_name": oauth_name,
            "access_token": access_token,
            "account_id": account_id,
            "account_email": account_email,
            "expires_at": expires_at,
            "refresh_token": refresh_token,
        }

        try:
            user = await self.get_by_oauth_account(oauth_name, account_id)
        except exceptions.UserNotExists:
            try:
                # Associate account
                user = await self.get_by_email(account_email)
                if not associate_by_email:
                    raise exceptions.UserAlreadyExists()
                user = await users.add_oauth_account(
                    self.database, user, oauth_account_dict, roles=roles
                )
            except exceptions.UserNotExists:
                # Create account
                user = await users.create_oauth_user(
                    self.database,
                    self.user_schema,
                    email=account_email,
                    is_verified=is_verified_by_default,
                    account=oauth_account_dict,
                    roles=roles,
                )
                await self.on_after_register(user, request)
        else:
            # Update oauth
            user = await users.update_oauth_account(
                self.database, user, oauth_name, account_id, oauth_account_dict
            )

        return user

    async def on_after_register(
        self, user: models.UP, request: Optional[Request] = None
    ) -> None:
        """
        Perform logic after successful user registration.

        *You should overload this method to add your own logic.*

        :param user: The registered user
        :param request: Optional FastAPI request that
        triggered the operation, defaults to None.
        """
        return  # pragma: no cover

    async def on_after_login(
        self,
        user: models.UP,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
    ) -> None:
        """
        Perform logic after user login: the on_after_login callback, if given.

        :param user: The user that is logging in
        :param request: Optional FastAPI request
        :param response: Optional response built by the transport.
        Defaults to None
        """
        if self._on_after_login is not None:
            await self._on_after_login(user)

    def _get_permitted_roles(self, oauth_name: str, email: str) -> Set[str]:
        """Gets the roles the provider grants, once its rules permit the email

        :raises UnsupportedProvider: The provider has no rules.
        :raises EmailNotPermitted: The email does not match the provider's email_regex.
        """
        if self.providers is None:
            return set()
        provider = self.providers.get(oauth_name)
        if provider is None:
            raise exceptions.UnsupportedProvider("this oauth login type not supported")
        if re.match(provider.email_regex, email) is None:
            raise exceptions.EmailNotPermitted("user not permitted")
        return set(provider.roles)


UserManagerDependency = DependencyCallable[BaseUserManager[models.UP, models.ID]]
