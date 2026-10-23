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

"""A collection of routers for the app_tokens submodule of the auth service"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.requests import Request
from fastapi_users import schemas

from libs.storage import Id

from ..projects.manager import ProjectAppTokenManager, ProjectManagerDependency
from ..users.dtos import CurrentUserIdDependency
from .auth_backend import AppTokenAuthenticationBackend
from .dtos import AppTokenCreate, AppTokenListResponse, AppTokenRead, AppTokenUpdate
from .strategy import AppTokenStrategy


def get_app_tokens_router(
    backend: AppTokenAuthenticationBackend,
    get_project_manager: "ProjectManagerDependency",
    get_current_user_id: "CurrentUserIdDependency",
    **kwargs,
) -> APIRouter:
    """Generate a router with login/logout routes for an authentication backend."""
    router = APIRouter()

    @router.get(
        "/{id}",
        response_model=AppTokenRead,
        name="app_tokens:my_app_token",
    )
    async def get_my_app_token(
        id: Id,
        user_id: str = Depends(get_current_user_id),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ):
        app_tokens = await project_manager.find_app_tokens(user_id, ids=[id], limit=1)

        try:
            return schemas.model_validate(AppTokenRead, app_tokens[0])
        except IndexError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="the token does not exist.",
            )

    # route to view list of app tokens
    @router.get(
        "/",
        response_model=AppTokenListResponse,
        name="app_tokens:my_many_app_tokens",
    )
    async def get_my_app_tokens(
        user_id: str = Depends(get_current_user_id),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
        skip: int = Query(0),
        limit: Optional[int] = Query(None),
        ids: Optional[List[Id]] = Query(None, alias="id"),
        project_id: Optional[List[Id]] = Query(None),
        title: Optional[List[str]] = Query(None),
        min_lifespan_seconds: Optional[int] = Query(None),
        max_lifespan_seconds: Optional[int] = Query(None),
    ):
        app_tokens = await project_manager.find_app_tokens(
            user_id,
            ids=ids,
            project_ids=project_id,
            titles=title,
            min_lifespan_seconds=min_lifespan_seconds,
            max_lifespan_seconds=max_lifespan_seconds,
            skip=skip,
            limit=limit,
        )

        data = [schemas.model_validate(AppTokenRead, token) for token in app_tokens]
        return AppTokenListResponse(data=data, skip=skip, limit=limit)

    # route to generate tokens
    @router.post(
        "/",
        name=f"app_tokens:{backend.name}.generate_token",
        responses=backend.transport.get_openapi_login_responses_success(),
    )
    async def generate_app_token(
        request: Request,
        payload: AppTokenCreate,
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
        strategy: AppTokenStrategy = Depends(backend.get_strategy),
        user_id: str = Depends(get_current_user_id),
    ):
        project = await project_manager.authenticate(details=payload, user_id=user_id)

        if project is None or not project.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        response = await backend.generate_token(
            strategy=strategy, payload=payload, user_id=user_id
        )
        return response

    # route to update tokens
    @router.put(
        "/{_id}",
        name=f"app_tokens:{backend.name}.update_token",
        responses={200: {"model": AppTokenRead}},
    )
    async def update_app_token(
        _id: Id,
        payload: AppTokenUpdate,
        strategy: AppTokenStrategy = Depends(backend.get_strategy),
        user_id: str = Depends(get_current_user_id),
    ):
        updated_token = await backend.update_token(
            strategy=strategy, _id=_id, payload=payload, user_id=user_id
        )
        if updated_token is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        return schemas.model_validate(AppTokenRead, updated_token).model_dump(
            mode="json"
        )

    # route to destroy tokens
    @router.delete(
        "/{_id}",
        name=f"app_tokens:{backend.name}.destroy_token",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def destroy(
        _id: Id,
        user_id: str = Depends(get_current_user_id),
        strategy: AppTokenStrategy = Depends(backend.get_strategy),
    ):
        return await backend.destroy_token(strategy=strategy, _id=_id, user_id=user_id)

    return router
