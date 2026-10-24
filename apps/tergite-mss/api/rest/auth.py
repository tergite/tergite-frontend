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

"""The auth backends and the current user and project dependencies"""
from typing import Optional, Tuple

from beanie import PydanticObjectId
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

import settings
from libs.storage import Database
from services import auth

from .database import get_database
from .users import get_user_manager

JWT_HEADER_BACKEND = auth.get_jwt_header_backend(
    login_url="/auth/jwt/login",
    jwt_secret=settings.CONFIG.auth.jwt_secret,
    lifetime_seconds=settings.CONFIG.auth.jwt_ttl,
)
JWT_COOKIE_BACKEND = auth.get_jwt_cookie_backend(
    jwt_secret=settings.CONFIG.auth.jwt_secret,
    cookie_max_age=settings.CONFIG.auth.jwt_ttl,
    cookie_name=settings.CONFIG.auth.cookie_name,
    cookie_domain=settings.CONFIG.auth.cookie_domain,
)
JWT_AUTH = auth.UserBasedAuth[auth.User, PydanticObjectId](
    get_user_manager, [JWT_HEADER_BACKEND, JWT_COOKIE_BACKEND]
)

GET_CURRENT_USER = JWT_AUTH.current_user(active=True)
GET_CURRENT_USER_ID = JWT_AUTH.current_user_id()
GET_CURRENT_SUPERUSER = JWT_AUTH.current_user(active=True, superuser=True)

APP_TOKEN_SCHEME = OAuth2PasswordBearer(tokenUrl="/me/tokens/", auto_error=False)


async def get_app_token_owner(
    database: Database = Depends(get_database),
    token: Optional[str] = Depends(APP_TOKEN_SCHEME),
) -> Optional[auth.TokenOwner]:
    """Dependency injector of the project and user of the request's app token, if any"""
    if token is None:
        return None
    return await auth.get_token_owner(database, token)


async def get_current_lax_owner(
    owner: Optional[auth.TokenOwner] = Depends(get_app_token_owner),
) -> auth.TokenOwner:
    """Dependency injector of the app token's project and user, under the lax rule"""
    return auth.check_project_access(owner, auth.LAX)


async def get_current_project_user_ids(
    owner: Optional[auth.TokenOwner] = Depends(get_app_token_owner),
) -> Tuple[str, str]:
    """Dependency injector of the app token's project and user ids, under the strict rule"""
    owner = auth.check_project_access(owner, auth.STRICT)
    return owner.project.id, str(owner.user.id)
