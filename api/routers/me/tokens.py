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
"""Routes for the app tokens the current user generates"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from api.dependencies import AppTokenQueryDep, CurrentUserIdDep, DatabaseDep
from libs.storage import Id
from services import auth
from services.auth import (
    AppTokenCreate,
    AppTokenListResponse,
    AppTokenQuery,
    AppTokenRead,
    AppTokenUpdate,
    BearerResponse,
)

router = APIRouter()


@router.get(
    "/{id}",
    response_model=AppTokenRead,
    name="app_tokens:my_app_token",
)
async def get_my_app_token(
    database: DatabaseDep, id: Id, user_id: CurrentUserIdDep
) -> AppTokenRead:
    app_tokens = await auth.find_app_tokens(
        database, user_id, AppTokenQuery(ids=[id]), limit=1
    )
    if not app_tokens:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="the token does not exist.",
        )
    return AppTokenRead.model_validate(app_tokens[0])


@router.get(
    "/",
    response_model=AppTokenListResponse,
    name="app_tokens:my_many_app_tokens",
)
async def get_my_app_tokens(
    database: DatabaseDep,
    user_id: CurrentUserIdDep,
    query: AppTokenQueryDep,
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
) -> AppTokenListResponse:
    app_tokens = await auth.find_app_tokens(
        database, user_id, query, skip=skip, limit=limit
    )
    data = [AppTokenRead.model_validate(app_token) for app_token in app_tokens]
    return AppTokenListResponse(data=data, skip=skip, limit=limit)


@router.post(
    "/",
    name="app_tokens:app-token.generate_token",
    response_model=None,
    responses={status.HTTP_200_OK: {"model": BearerResponse}},
)
async def generate_app_token(
    database: DatabaseDep, payload: AppTokenCreate, user_id: CurrentUserIdDep
) -> BearerResponse:
    app_token = await auth.create_app_token(database, payload, user_id=user_id)
    return BearerResponse(access_token=app_token.token, token_type="bearer")


@router.put(
    "/{_id}",
    response_model=AppTokenRead,
    name="app_tokens:app-token.update_token",
)
async def update_app_token(
    database: DatabaseDep, _id: Id, payload: AppTokenUpdate, user_id: CurrentUserIdDep
) -> AppTokenRead:
    app_token = await auth.update_app_token_expiry(
        database, _id, user_id=user_id, expires_at=payload.expires_at
    )
    if app_token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return AppTokenRead.model_validate(app_token)


@router.delete(
    "/{_id}",
    name="app_tokens:app-token.destroy_token",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def destroy(database: DatabaseDep, _id: Id, user_id: CurrentUserIdDep) -> None:
    await auth.delete_app_token(database, _id, user_id=user_id)
