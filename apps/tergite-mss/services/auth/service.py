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
import re
from typing import List, Optional

import motor.motor_asyncio
from fastapi import APIRouter
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend

from libs.storage import Database
from utils.config import AuthConfig, Oauth2ClientConfig, ProjectsConfig
from utils.mongodb import init_strict_beanie

from . import projects, providers, users
from .users.dtos import User
from .utils import get_oauth2_client


async def on_startup(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    database: Database,
    conf: AuthConfig,
    projects_conf: ProjectsConfig,
) -> None:
    """Runs init operations when the application is starting up

    Args:
        db: the mongo database where the users are stored
        database: the database where the projects and app tokens are stored
        conf: the auth configuration, whose clients decide who may sign in and how
        projects_conf: the projects configuration
    """
    users.set_auth_clients(conf.clients)
    providers.set_auth_providers(conf.clients)
    projects.on_startup(database, conf=projects_conf)
    await init_strict_beanie(
        database=db,
        document_models=[
            users.dtos.User,
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
            is_verified_by_default=conf.is_verified_by_default,
            associate_by_email=conf.associate_by_email,
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
            is_verified_by_default=conf.is_verified_by_default,
            associate_by_email=conf.associate_by_email,
            redirect_url=conf.redirect_url,
        ),
        prefix=f"/app/{client.name}",
        tags=tags,
    )


async def get_user_emails(search: Optional[str] = None, limit: int = 20) -> List[str]:
    """Gets user email addresses, alphabetically

    Returns addresses alone, never the user records: the callers that may see this
    are completing a form, not reading a directory.

    Args:
        search: a case-insensitive substring of the address; omit for the first page
        limit: the maximum number of addresses to return

    Returns:
        the matched email addresses
    """
    filter_obj = {}
    if search:
        # escaped, or a caller could hand us a regex to evaluate
        filter_obj["email"] = {"$regex": re.escape(search), "$options": "i"}

    records = await User.find(filter_obj, limit=limit, sort="email").to_list()
    return [user.email for user in records]
