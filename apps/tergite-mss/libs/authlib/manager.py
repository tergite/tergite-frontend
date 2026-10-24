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
import uuid
from typing import Any, Generic, Optional

from fastapi import Request, Response
from fastapi.security import OAuth2PasswordRequestForm

from libs.authlib import exceptions, models
from libs.authlib.db import BaseUserDatabase
from libs.authlib.password import PasswordHelper, PasswordHelperProtocol
from libs.authlib.types import DependencyCallable


class BaseUserManager(Generic[models.UP, models.ID]):
    """
    User management logic.

    :attribute reset_password_token_secret: Secret to encode reset password token.
    :attribute reset_password_token_lifetime_seconds: Lifetime of reset password token.
    :attribute reset_password_token_audience: JWT audience of reset password token.
    :attribute verification_token_secret: Secret to encode verification token.
    :attribute verification_token_lifetime_seconds: Lifetime of verification token.
    :attribute verification_token_audience: JWT audience of verification token.

    :param user_db: Database adapter instance.
    """

    user_db: BaseUserDatabase[models.UP, models.ID]
    password_helper: PasswordHelperProtocol

    def __init__(
        self,
        user_db: BaseUserDatabase[models.UP, models.ID],
        password_helper: Optional[PasswordHelperProtocol] = None,
    ):
        self.user_db = user_db
        if password_helper is None:
            self.password_helper = PasswordHelper()
        else:
            self.password_helper = password_helper  # pragma: no cover

    def parse_id(self, value: Any) -> models.ID:
        """
        Parse a value into a correct models.ID instance.

        :param value: The value to parse.
        :raises InvalidID: The models.ID value is invalid.
        :return: An models.ID object.
        """
        raise NotImplementedError()  # pragma: no cover

    async def get(self, id: models.ID) -> models.UP:
        """
        Get a user by id.

        :param id: Id. of the user to retrieve.
        :raises UserNotExists: The user does not exist.
        :return: A user.
        """
        user = await self.user_db.get(id)

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
        user = await self.user_db.get_by_email(user_email)

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
        user = await self.user_db.get_by_oauth_account(oauth, account_id)

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
        :return: A user.
        """
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
                user = await self.user_db.add_oauth_account(user, oauth_account_dict)
            except exceptions.UserNotExists:
                # Create account
                password = self.password_helper.generate()
                user_dict = {
                    "email": account_email,
                    "hashed_password": self.password_helper.hash(password),
                    "is_verified": is_verified_by_default,
                }
                user = await self.user_db.create(user_dict)
                user = await self.user_db.add_oauth_account(user, oauth_account_dict)
                await self.on_after_register(user, request)
        else:
            # Update oauth
            for existing_oauth_account in user.oauth_accounts:
                if (
                    existing_oauth_account.account_id == account_id
                    and existing_oauth_account.oauth_name == oauth_name
                ):
                    user = await self.user_db.update_oauth_account(
                        user, existing_oauth_account, oauth_account_dict
                    )

        return user

    async def oauth_associate_callback(
        self: "BaseUserManager[models.UOAP, models.ID]",
        user: models.UOAP,
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: Optional[int] = None,
        refresh_token: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> models.UOAP:
        """
        Handle the callback after a successful OAuth association.

        We add this new OAuth account to the given user.

        :param oauth_name: Name of the OAuth client.
        :param access_token: Valid access token for the service provider.
        :param account_id: models.ID of the user on the service provider.
        :param account_email: E-mail of the user on the service provider.
        :param expires_at: Optional timestamp at which the access token expires.
        :param refresh_token: Optional refresh token to get a
        fresh access token from the service provider.
        :param request: Optional FastAPI request that
        triggered the operation, defaults to None
        :return: A user.
        """
        oauth_account_dict = {
            "oauth_name": oauth_name,
            "access_token": access_token,
            "account_id": account_id,
            "account_email": account_email,
            "expires_at": expires_at,
            "refresh_token": refresh_token,
        }

        user = await self.user_db.add_oauth_account(user, oauth_account_dict)

        await self.on_after_update(user, {}, request)

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

    async def on_after_update(
        self,
        user: models.UP,
        update_dict: dict[str, Any],
        request: Optional[Request] = None,
    ) -> None:
        """
        Perform logic after successful user update.

        *You should overload this method to add your own logic.*

        :param user: The updated user
        :param update_dict: Dictionary with the updated user fields.
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
        Perform logic after user login.

        *You should overload this method to add your own logic.*

        :param user: The user that is logging in
        :param request: Optional FastAPI request
        :param response: Optional response built by the transport.
        Defaults to None
        """
        return  # pragma: no cover

    async def authenticate(
        self, credentials: OAuth2PasswordRequestForm
    ) -> Optional[models.UP]:
        """
        Authenticate and return a user following an email and a password.

        Will automatically upgrade password hash if necessary.

        :param credentials: The user credentials.
        """
        try:
            user = await self.get_by_email(credentials.username)
        except exceptions.UserNotExists:
            # Run the hasher to mitigate timing attack
            # Inspired from Django: https://code.djangoproject.com/ticket/20760
            self.password_helper.hash(credentials.password)
            return None

        verified, updated_password_hash = self.password_helper.verify_and_update(
            credentials.password, user.hashed_password
        )
        if not verified:
            return None
        # Update password hash to a more robust one if needed
        if updated_password_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_password_hash})

        return user


class UUIDIDMixin:
    def parse_id(self, value: Any) -> uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(value)
        except ValueError as e:
            raise exceptions.InvalidID() from e


class IntegerIDMixin:
    def parse_id(self, value: Any) -> int:
        if isinstance(value, float):
            raise exceptions.InvalidID()
        try:
            return int(value)
        except ValueError as e:
            raise exceptions.InvalidID() from e


UserManagerDependency = DependencyCallable[BaseUserManager[models.UP, models.ID]]
