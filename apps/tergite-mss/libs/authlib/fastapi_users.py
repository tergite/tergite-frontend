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
from collections.abc import Mapping, Sequence
from typing import Generic

from fastapi import APIRouter

from libs.authlib import models
from libs.authlib.authentication import AuthenticationBackend, Authenticator
from libs.authlib.jwt import SecretType
from libs.authlib.manager import UserManagerDependency
from libs.authlib.providers import OAuthProvider
from libs.authlib.router import get_auth_router, get_oauth_router


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
        self.get_current_user_id = self.authenticator.get_current_user_id

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
            self.authenticator,
            requires_verification,
        )

    def get_oauth_router(
        self,
        providers: Mapping[str, OAuthProvider],
        backend: AuthenticationBackend[models.UP, models.ID],
        state_secret: SecretType,
        should_add_app_alias: bool = False,
    ) -> APIRouter:
        """
        Return the OAuth router of the providers, each named in its routes' paths.

        :param providers: The providers by name.
        :param backend: The authentication backend instance.
        :param state_secret: Secret used to encode the state JWT.
        :param should_add_app_alias: Whether the routes are also served under /app.
        """
        return get_oauth_router(
            providers,
            backend,
            self.get_user_manager,
            state_secret,
            should_add_app_alias,
        )
