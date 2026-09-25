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

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.requests import Request
from fastapi_users import schemas

from ..projects.manager import ProjectAppTokenManager, ProjectManagerDependency
from ..users.dtos import CurrentUserIdDependency
from ..users.manager import UserManager, UserManagerDependency
from ..utils import MAX_LIST_QUERY_LEN, TooManyListQueryParams
from .auth_backend import AppTokenAuthenticationBackend
from .dtos import AppTokenCreate, AppTokenListResponse, AppTokenRead, AppTokenUpdate
from .strategy import AppTokenStrategy


def get_app_tokens_router(
    backend: AppTokenAuthenticationBackend,
    get_project_manager: "ProjectManagerDependency",
    get_user_manager: "UserManagerDependency",
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
        id: PydanticObjectId,
        user_id: str = Depends(get_current_user_id),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
        user_manager: UserManager = Depends(get_user_manager),
    ):
        parsed_user_id = user_manager.parse_id(user_id)
        filter_obj = {"user_id": parsed_user_id, "_id": id}

        app_tokens = await project_manager.get_many_app_tokens(
            filter_obj=filter_obj,
        )

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
        user_manager: UserManager = Depends(get_user_manager),
        skip: int = Query(0),
        limit: Optional[int] = Query(None),
        ids: Optional[List[PydanticObjectId]] = Query(None, alias="id"),
        project_id: Optional[List[PydanticObjectId]] = Query(None),
        title: Optional[List[str]] = Query(None),
        min_lifespan_seconds: Optional[int] = Query(None),
        max_lifespan_seconds: Optional[int] = Query(None),
    ):
        parsed_user_id = user_manager.parse_id(user_id)
        filter_obj = {"user_id": parsed_user_id}

        if ids is not None:
            if len(ids) > MAX_LIST_QUERY_LEN:
                raise TooManyListQueryParams(
                    "id", expected=MAX_LIST_QUERY_LEN, got=len(ids)
                )

            filter_obj["_id"] = {"$in": ids}

        if project_id is not None:
            if len(project_id) > MAX_LIST_QUERY_LEN:
                raise TooManyListQueryParams(
                    "project_id",
                    expected=MAX_LIST_QUERY_LEN,
                    got=len(project_id),
                )

            filter_obj["project_id"] = {"$in": project_id}

        if title is not None:
            if len(title) > MAX_LIST_QUERY_LEN:
                raise TooManyListQueryParams(
                    "title", expected=MAX_LIST_QUERY_LEN, got=len(title)
                )

            filter_obj["title"] = {"$in": title}

        if min_lifespan_seconds is not None:
            filter_obj["lifespan_seconds"] = {"$gte": min_lifespan_seconds}

        if max_lifespan_seconds is not None:
            if "lifespan_seconds" not in filter_obj:
                filter_obj["lifespan_seconds"] = {}

            filter_obj["lifespan_seconds"].update({"$lte": max_lifespan_seconds})

        app_tokens = await project_manager.get_many_app_tokens(
            filter_obj=filter_obj, skip=skip, limit=limit
        )

        data = [schemas.model_validate(AppTokenRead, token) for token in app_tokens]
        return AppTokenListResponse(data=data, skip=skip, limit=limit)

    # route to generate tokens
    @router.post(
        "/",
        name=f"app_tokens:{backend.name}.generate_token",
    )
    async def generate_app_token(
        request: Request,
        payload: AppTokenCreate,
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
        user_manager: UserManager = Depends(get_user_manager),
        strategy: AppTokenStrategy = Depends(backend.get_strategy),
        user_id: str = Depends(get_current_user_id),
    ):
        project = await project_manager.authenticate(
            details=payload, user_id=PydanticObjectId(user_id)
        )

        if project is None or not project.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        parsed_user_id = user_manager.parse_id(user_id)
        response = await backend.generate_token(
            strategy=strategy, payload=payload, user_id=parsed_user_id
        )
        return response

    # route to update tokens
    @router.put(
        "/{_id}",
        name=f"app_tokens:{backend.name}.update_token",
    )
    async def update_app_token(
        _id: PydanticObjectId,
        payload: AppTokenUpdate,
        user_manager: UserManager = Depends(get_user_manager),
        strategy: AppTokenStrategy = Depends(backend.get_strategy),
        user_id: str = Depends(get_current_user_id),
    ):
        parsed_user_id = user_manager.parse_id(user_id)
        updated_token = await backend.update_token(
            strategy=strategy, _id=_id, payload=payload, user_id=parsed_user_id
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
    )
    async def destroy(
        _id: PydanticObjectId,
        user_id: str = Depends(get_current_user_id),
        user_manager: UserManager = Depends(get_user_manager),
        strategy: AppTokenStrategy = Depends(backend.get_strategy),
    ):
        parsed_user_id = user_manager.parse_id(user_id)
        return await backend.destroy_token(
            strategy=strategy, _id=_id, user_id=parsed_user_id
        )

    return router
