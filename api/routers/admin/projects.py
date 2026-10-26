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
"""Routes for superusers to manage every project"""

import asyncio
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.dependencies import CurrentSuperuserDep, DatabaseDep, ProjectQueryDep
from libs.storage import is_id
from services import auth
from services.auth import (
    Project,
    ProjectAdminView,
    ProjectCreate,
    ProjectUpdate,
)
from utils.api import PaginatedListResponse

router = APIRouter()


async def get_project_or_404(database: DatabaseDep, id: str) -> Project:
    """Gets the project of the path's id; a malformed id is as missing as an unknown one"""
    if not is_id(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        return await auth.get_project(database, id)
    except auth.ProjectNotExists as exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exp


ProjectOr404Dep = Annotated[Project, Depends(get_project_or_404)]


@router.post(
    "/",
    response_model=ProjectAdminView,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    name="projects:create_project",
)
async def create(
    database: DatabaseDep, payload: ProjectCreate, actor: CurrentSuperuserDep
) -> ProjectAdminView:
    try:
        project = await auth.create_project(database, payload, actor=actor)
    except auth.ProjectExists as exp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=auth.ExtendedErrorCode.PROJECT_ALREADY_EXISTS,
        ) from exp
    return await auth.get_admin_view(database, project)


@router.get(
    "/{id}",
    name="projects:single_project",
    responses={
        status.HTTP_200_OK: {"model": ProjectAdminView},
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Missing token or inactive project."
        },
        status.HTTP_403_FORBIDDEN: {"description": "Not a superuser."},
        status.HTTP_404_NOT_FOUND: {"description": "The project does not exist."},
    },
)
async def get_project(
    database: DatabaseDep, requester: CurrentSuperuserDep, project: ProjectOr404Dep
) -> ProjectAdminView:
    return await auth.get_admin_view(database, project)


@router.get(
    "/",
    response_model=PaginatedListResponse[ProjectAdminView],
    name="projects:many_projects",
)
async def get_many_projects(
    database: DatabaseDep,
    requester: CurrentSuperuserDep,
    query: ProjectQueryDep,
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
) -> PaginatedListResponse[ProjectAdminView]:
    projects = await auth.find_projects(database, query, skip=skip, limit=limit)
    data = await asyncio.gather(
        *(auth.get_admin_view(database, project) for project in projects)
    )
    return PaginatedListResponse(data=data, skip=skip, limit=limit)


@router.put(
    "/{id}",
    response_model=ProjectAdminView,
    response_model_exclude_none=True,
    name="projects:put_project",
)
async def update_project(
    database: DatabaseDep,
    payload: ProjectUpdate,
    actor: CurrentSuperuserDep,
    project: ProjectOr404Dep,
) -> ProjectAdminView:
    updated_project = await auth.update_project(database, project, payload, actor=actor)
    return await auth.get_admin_view(database, updated_project)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    name="projects:delete_project",
)
async def delete_project(
    database: DatabaseDep, requester: CurrentSuperuserDep, project: ProjectOr404Dep
) -> None:
    await auth.delete_project(database, project, is_superuser=True)
    return None
