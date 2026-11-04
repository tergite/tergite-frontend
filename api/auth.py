# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""The app's auth, built from the auth config, and the current user and project
dependencies"""

from functools import partial
from typing import Optional, Tuple

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

import settings
from libs import authlib
from libs.storage import Database
from services import auth

from .database import get_database

AUTH = authlib.Auth(
    get_database,
    auth.User,
    providers={
        client.name: authlib.OAuthProvider(
            client=auth.get_oauth2_client(client),
            email_regex=client.email_regex,
            roles=tuple(client.roles),
            redirect_url=client.redirect_url,
            should_associate_by_email=client.associate_by_email,
            is_verified_by_default=client.is_verified_by_default,
        )
        for client in settings.CONFIG.auth.clients
    },
    secret=settings.CONFIG.auth.jwt_secret,
    session_lifetime_seconds=settings.CONFIG.auth.jwt_ttl,
    cookie=authlib.SessionCookie(
        name=settings.CONFIG.auth.cookie_name,
        max_age=settings.CONFIG.auth.jwt_ttl,
        domain=settings.CONFIG.auth.cookie_domain,
    ),
    on_after_login=partial(
        auth.ensure_personal_project,
        qpu_seconds=settings.CONFIG.projects.personal_qpu_seconds,
    ),
)

GET_CURRENT_USER = AUTH.get_current_user(should_require_active=True)
GET_CURRENT_USER_ID = AUTH.get_current_user_id()
GET_CURRENT_SUPERUSER = AUTH.get_current_user(
    should_require_active=True, should_require_superuser=True
)

APP_TOKEN_SCHEME = OAuth2PasswordBearer(tokenUrl="/me/tokens/", auto_error=False)


async def get_app_token_owner(
    database: Database = Depends(get_database),
    token: Optional[str] = Depends(APP_TOKEN_SCHEME),
) -> Optional[auth.TokenOwner]:
    """Dependency injector of the project and user of the request's app token, if any

    Args:
        database: the database where the app tokens are stored
        token: the app token from the request's bearer header, if sent

    Returns:
        the token's project and user, or None if no token was sent
    """
    if token is None:
        return None
    return await auth.get_token_owner(database, token)


async def get_current_lax_owner(
    owner: Optional[auth.TokenOwner] = Depends(get_app_token_owner),
) -> auth.TokenOwner:
    """Dependency injector of the app token's project and user, under the lax rule

    Args:
        owner: the project and user of the request's app token, if any

    Returns:
        the token's project and user, once allowed under the lax rule

    Raises:
        UnauthorizedError: there is no valid token, or its project or user is inactive
    """
    return auth.check_project_access(owner, auth.LAX)


async def get_current_project_user_ids(
    owner: Optional[auth.TokenOwner] = Depends(get_app_token_owner),
) -> Tuple[str, str]:
    """Dependency injector of the app token's project and user ids, under the strict rule

    Args:
        owner: the project and user of the request's app token, if any

    Returns:
        the project id and the user id, once allowed under the strict rule

    Raises:
        UnauthorizedError: there is no valid token, or its project or user is inactive
        ForbiddenError: the project has no QPU seconds left
    """
    owner = auth.check_project_access(owner, auth.STRICT)
    return owner.project.id, str(owner.user.id)
