# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Router for auth related operations"""
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, FastAPI, Query
from loguru import logger

import settings
from api.rest.auth import JWT_AUTH, JWT_COOKIE_BACKEND
from services.auth import AuthProvider, providers, register_oauth2_client
from services.auth.providers.dtos import AuthProviderQuery
from utils.api import PaginatedListResponse, build_paginated_json
from utils.config import Oauth2ClientConfig


def include_auth_router(root_router: Union[APIRouter, FastAPI]):
    """Includes auth router on the root router

    Args:
        root_router: the root router to add the auth router to
    """
    router = APIRouter(prefix="/auth", tags=["auth"])

    # Oauth clients for authentication
    for client in settings.CONFIG.auth.clients:
        client_conf = Oauth2ClientConfig.model_validate(client)
        logger.info(f"Registering OAuth2 client provider: {client_conf.name}")
        register_oauth2_client(
            router,
            controller=JWT_AUTH,
            auth_cookie_backend=JWT_COOKIE_BACKEND,
            jwt_secret=settings.CONFIG.auth.jwt_secret,
            conf=client_conf,
            tags=["auth"],
        )

    # both login and logout
    router.include_router(
        JWT_AUTH.get_auth_router(
            backend=JWT_COOKIE_BACKEND, requires_verification=True
        ),
        prefix="",
        tags=["auth"],
    )

    @router.get(
        "/providers/", responses={200: {"model": PaginatedListResponse[AuthProvider]}}
    )
    def get_auth_providers(
        query: AuthProviderQuery = Depends(),
        skip: int = 0,
        limit: Optional[int] = None,
        sort: List[str] = Query(("name",)),
    ):
        """Returns the auth provider given an existing email domain"""
        filters = query.model_dump()
        data = providers.get_many(filters=filters, skip=skip, limit=limit, sort=sort)

        return build_paginated_json(
            data, skip=skip, limit=limit, should_exclude_none=False
        )

    root_router.include_router(router)
