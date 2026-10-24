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
from collections.abc import Sequence
from typing import Generic, Optional

from fastapi import APIRouter

from libs.authlib import models, schemas
from libs.authlib.authentication import AuthenticationBackend, Authenticator
from libs.authlib.jwt import SecretType
from libs.authlib.manager import UserManagerDependency
from libs.authlib.router import get_auth_router

try:
    from httpx_oauth.oauth2 import BaseOAuth2

    from libs.authlib.router import get_oauth_router
    from libs.authlib.router.oauth import get_oauth_associate_router
except ModuleNotFoundError:  # pragma: no cover
    BaseOAuth2 = type  # type: ignore


class FastAPIUsers(Generic[models.UP, models.ID]):
    """
    Main object that ties together the component for users authentication.

    :param get_user_manager: Dependency callable getter to inject the
    user manager class instance.
    :param auth_backends: List of authentication backends.

    :attribute current_user: Dependency callable getter to inject authenticated user
    with a specific set of parameters.
    """

    authenticator: Authenticator[models.UP, models.ID]

    def __init__(
        self,
        get_user_manager: UserManagerDependency[models.UP, models.ID],
        auth_backends: Sequence[AuthenticationBackend[models.UP, models.ID]],
    ):
        self.authenticator = Authenticator(auth_backends, get_user_manager)
        self.get_user_manager = get_user_manager
        self.current_user = self.authenticator.current_user

    def get_auth_router(
        self,
        backend: AuthenticationBackend[models.UP, models.ID],
        requires_verification: bool = False,
    ) -> APIRouter:
        """
        Return an auth router for a given authentication backend.

        :param backend: The authentication backend instance.
        :param requires_verification: Whether the authentication
        require the user to be verified or not. Defaults to False.
        """
        return get_auth_router(
            backend,
            self.get_user_manager,
            self.authenticator,
            requires_verification,
        )

    def get_oauth_router(
        self,
        oauth_client: BaseOAuth2,
        backend: AuthenticationBackend[models.UP, models.ID],
        state_secret: SecretType,
        redirect_url: Optional[str] = None,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
    ) -> APIRouter:
        """
        Return an OAuth router for a given OAuth client and authentication backend.

        :param oauth_client: The HTTPX OAuth client instance.
        :param backend: The authentication backend instance.
        :param state_secret: Secret used to encode the state JWT.
        :param redirect_url: Optional arbitrary redirect URL for the OAuth2 flow.
        If not given, the URL to the callback endpoint will be generated.
        :param associate_by_email: If True, any existing user with the same
        e-mail address will be associated to this user. Defaults to False.
        :param is_verified_by_default: If True, the `is_verified` flag will be
        set to `True` on newly created user. Make sure the OAuth Provider you're
        using does verify the email address before enabling this flag.
        """
        return get_oauth_router(
            oauth_client,
            backend,
            self.get_user_manager,
            state_secret,
            redirect_url,
            associate_by_email,
            is_verified_by_default,
        )

    def get_oauth_associate_router(
        self,
        oauth_client: BaseOAuth2,
        user_schema: type[schemas.U],
        state_secret: SecretType,
        redirect_url: Optional[str] = None,
        requires_verification: bool = False,
    ) -> APIRouter:
        """
        Return an OAuth association router for a given OAuth client.

        :param oauth_client: The HTTPX OAuth client instance.
        :param user_schema: Pydantic schema of a public user.
        :param state_secret: Secret used to encode the state JWT.
        :param redirect_url: Optional arbitrary redirect URL for the OAuth2 flow.
        If not given, the URL to the callback endpoint will be generated.
        :param requires_verification: Whether the endpoints
        require the users to be verified or not. Defaults to False.
        """
        return get_oauth_associate_router(
            oauth_client,
            self.authenticator,
            self.get_user_manager,
            user_schema,
            state_secret,
            redirect_url,
            requires_verification,
        )
