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
"""Routes for the projects the current user belongs to"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, status

from api.dependencies import (
    CurrentUserDep,
    CurrentUserIdDep,
    DatabaseDep,
    ProjectQueryDep,
)
from libs.storage import Id, is_id
from services import auth
from services.auth import ProjectRead
from utils.api import PaginatedListResponse, get_paginated_json

router = APIRouter()


@router.get(
    "/",
    name="projects:my_many_projects",
    response_model=None,
    responses={200: {"model": PaginatedListResponse[ProjectRead]}},
)
async def get_projects(
    database: DatabaseDep,
    user_id: CurrentUserIdDep,
    query: ProjectQueryDep,
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
) -> Dict[str, Any]:
    projects = await auth.find_projects(
        database, query, member_id=user_id, skip=skip, limit=limit
    )
    data = [ProjectRead.model_validate(project) for project in projects]
    return get_paginated_json(data, skip=skip, limit=limit)


@router.get(
    "/{id}",
    name="projects:my_single_project",
    response_model=None,
    responses={200: {"model": ProjectRead}},
)
async def get_project(
    database: DatabaseDep, id: str, user_id: CurrentUserIdDep
) -> Dict[str, Any]:
    # a malformed id is as missing as an unknown one: 404, not 422
    if not is_id(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        project = await auth.get_project(database, id)
    except auth.ProjectNotExists as exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exp

    if user_id not in project.members:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="the project does not exist.",
        )
    return ProjectRead.model_validate(project).model_dump(mode="json")


@router.delete(
    "/{_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="projects:remove_project_member",
)
async def remove_member(
    database: DatabaseDep, _id: Id, member_id: Id, user: CurrentUserDep
) -> None:
    """Removes a member from a project the caller administers, revoking their app tokens"""
    try:
        project = await auth.get_project(database, _id)
    except auth.ProjectNotExists as exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exp

    if project.admin_id != str(user.id) and not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if member_id == project.admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="the project admin cannot be removed",
        )
    if member_id not in project.user_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not a member"
        )

    await auth.remove_member(database, project, member_id, actor=user)
    return None


@router.delete(
    "/{_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="projects:destroy_my_administered_project",
)
async def destroy(database: DatabaseDep, _id: Id, user_id: CurrentUserIdDep) -> None:
    try:
        project = await auth.get_project(database, _id)
    except auth.ProjectNotExists as exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exp

    if user_id != project.admin_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # the service refuses a personal project unless the caller is a superuser
    await auth.delete_project(database, project)
    return None
