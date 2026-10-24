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

from api.rest.auth import AUTH
from libs import authlib
from services.auth import AuthProvider, providers
from services.auth.providers.dtos import AuthProviderQuery
from utils.api import PaginatedListResponse, get_paginated_json


def include_auth_router(root_router: Union[APIRouter, FastAPI]):
    """Includes auth router on the root router

    Args:
        root_router: the root router to add the auth router to
    """
    router = APIRouter(prefix="/auth", tags=["auth"])

    for provider_name in AUTH.providers:
        logger.info(f"Registering OAuth2 client provider: {provider_name}")
    router.include_router(authlib.get_oauth_router(AUTH, should_add_app_alias=True))
    router.include_router(authlib.get_logout_router(AUTH, should_require_verified=True))

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

        return get_paginated_json(
            data, skip=skip, limit=limit, should_exclude_none=False
        )

    root_router.include_router(router)
