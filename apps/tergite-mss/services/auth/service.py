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

"""Service for oauth2 authentication and project-based authorization"""
from typing import List

import motor.motor_asyncio
from beanie import PydanticObjectId, init_beanie
from fastapi import APIRouter
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend

import settings
from utils.config import Oauth2ClientConfig, UserRole

from . import app_tokens, projects, user_requests, users
from .utils import get_oauth2_client

# JWT-based authentication
JWT_HEADER_BACKEND = users.get_jwt_header_backend(
    login_url="/auth/jwt/login",
    jwt_secret=settings.CONFIG.auth.jwt_secret,
    lifetime_seconds=settings.CONFIG.auth.jwt_ttl,
)

JWT_COOKIE_BACKEND = users.get_jwt_cookie_backend(
    jwt_secret=settings.CONFIG.auth.jwt_secret,
    cookie_max_age=settings.CONFIG.auth.jwt_ttl,
    cookie_name=settings.CONFIG.auth.cookie_name,
    cookie_domain=settings.CONFIG.auth.cookie_domain,
)

JWT_AUTH = users.UserBasedAuth[users.dtos.User, PydanticObjectId](
    users.get_user_manager, [JWT_HEADER_BACKEND, JWT_COOKIE_BACKEND]
)

GET_CURRENT_USER = JWT_AUTH.current_user(active=True)
GET_CURRENT_USER_ID = JWT_AUTH.current_user_id()
GET_CURRENT_SUPERUSER = JWT_AUTH.current_user(active=True, superuser=True)
GET_USER_DB = users.get_user_db

# Project-based app token auth
# FIXME: the "auth/app-tokens/generate" does not matter
APP_TOKEN_BACKEND = projects.get_app_token_backend("auth/app-tokens/generate")
APP_TOKEN_AUTH = projects.ProjectBasedAuth(
    get_project_manager_dep=projects.get_project_manager,
    get_user_manager_dep=users.get_user_manager,
    get_current_user_dep=GET_CURRENT_USER,
    get_current_user_id_dep=GET_CURRENT_USER_ID,
    get_current_superuser_dep=GET_CURRENT_SUPERUSER,
    auth_backends=[APP_TOKEN_BACKEND],
)
GET_CURRENT_PROJECT = APP_TOKEN_AUTH.current_project(active=True)
GET_CURRENT_PROJECT_USER_IDS = APP_TOKEN_AUTH.current_project_and_user_ids(active=True)
GET_CURRENT_LAX_PROJECT = APP_TOKEN_AUTH.current_project(
    active=True, ignore_qpu_seconds=True
)
GET_CURRENT_SYSTEM_USER_PROJECT = APP_TOKEN_AUTH.current_project(
    active=True, user_roles=(UserRole.SYSTEM,)
)


async def on_startup(db: motor.motor_asyncio.AsyncIOMotorDatabase):
    """Runs init operations when the application is starting up"""
    await init_beanie(
        database=db,
        document_models=[
            users.dtos.User,
            app_tokens.dtos.AppToken,
            projects.dtos.Project,
            projects.dtos.DeletedProject,
            user_requests.dtos.UserRequest,
        ],
    )


def register_oauth2_client(
    router: APIRouter,
    controller: FastAPIUsers,
    auth_cookie_backend: AuthenticationBackend,
    jwt_secret: str,
    conf: Oauth2ClientConfig,
    tags: List[str] = ("auth",),
):
    """Registers an oauth2 method on the given router, allowing only browser based login and no REST API mode

    Args:
        router: APIRouter where to register the oauth2 method
        controller: the FastAPIUsers instance that controls authentication
        auth_cookie_backend: the AuthenticationBackend which handles the authentication via cookies
        jwt_secret: the secret string used to generate JWT tokens
        conf: the configuration for the oauth2 client
        tags: the list of tags to add to the routes of this client
    """
    client = get_oauth2_client(conf)

    # FIXME: There is still an issue with programmatically generating the redirect URI.
    #  It keeps missing the http(s). It is like the scheme is never passed along, which is weird

    # For browser based auth
    router.include_router(
        controller.get_oauth_router(
            oauth_client=client,
            backend=auth_cookie_backend,
            state_secret=jwt_secret,
            is_verified_by_default=True,
            redirect_url=conf.redirect_url,
        ),
        prefix=f"/{client.name}",
        tags=tags,
    )

    # For backward compatibility for now, we will also support the format of urls /auth/app/{client}/...
    router.include_router(
        controller.get_oauth_router(
            oauth_client=client,
            backend=auth_cookie_backend,
            state_secret=jwt_secret,
            is_verified_by_default=True,
            redirect_url=conf.redirect_url,
        ),
        prefix=f"/app/{client.name}",
        tags=tags,
    )
