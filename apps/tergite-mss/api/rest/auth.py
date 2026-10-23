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

"""The auth backends and current-user dependencies, built from the auth config"""
from beanie import PydanticObjectId

import settings
from services import auth

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
    auth.get_user_manager, [JWT_HEADER_BACKEND, JWT_COOKIE_BACKEND]
)

GET_CURRENT_USER = JWT_AUTH.current_user(active=True)
GET_CURRENT_USER_ID = JWT_AUTH.current_user_id()
GET_CURRENT_SUPERUSER = JWT_AUTH.current_user(active=True, superuser=True)

# FIXME: the "auth/app-tokens/generate" does not matter
APP_TOKEN_BACKEND = auth.get_app_token_backend("auth/app-tokens/generate")
APP_TOKEN_AUTH = auth.ProjectBasedAuth(
    get_project_manager_dep=auth.get_project_manager,
    get_user_manager_dep=auth.get_user_manager,
    get_current_user_dep=GET_CURRENT_USER,
    get_current_user_id_dep=GET_CURRENT_USER_ID,
    get_current_superuser_dep=GET_CURRENT_SUPERUSER,
    auth_backends=[APP_TOKEN_BACKEND],
)
GET_CURRENT_PROJECT_USER_IDS = APP_TOKEN_AUTH.current_project_and_user_ids(active=True)
GET_CURRENT_LAX_PROJECT_AND_USER = APP_TOKEN_AUTH.get_project_and_user(
    should_require_active=True, should_ignore_qpu_seconds=True
)
