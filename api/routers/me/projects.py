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
    """Gets a paginated list of the current user's projects that fit the given filters

    Args:
        database: the database where the projects are stored
        user_id: the id of the current logged-in user
        query: the filters the projects must fit
        skip: the number of projects to skip
        limit: the maximum number of projects to return

    Returns:
        the page of projects

    Raises:
        401: not logged in
    """
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
    """Gets the project of the given id, if the current user is a member of it

    Args:
        database: the database where the projects are stored
        id: the id of the project
        user_id: the id of the current logged-in user

    Returns:
        the project

    Raises:
        401: not logged in
        404: the project does not exist, or the user is not a member of it
    """
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
    return ProjectRead.model_validate(project).model_dump(
        mode="json", exclude_none=True
    )


@router.delete(
    "/{_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="projects:remove_project_member",
)
async def remove_member(
    database: DatabaseDep, _id: Id, member_id: Id, user: CurrentUserDep
) -> None:
    """Removes a member from a project the caller administers, revoking their app tokens

    Args:
        database: the database where the projects are stored
        _id: the id of the project
        member_id: the id of the member to remove
        user: the current logged-in user; the project's admin or a superuser

    Raises:
        400: the member is the project's admin
        401: not logged in
        403: the user neither administers the project nor is a superuser
        404: the project does not exist, or member_id is not one of its members
    """
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
    """Deletes a project the current user administers, with its app tokens

    Args:
        database: the database where the projects are stored
        _id: the id of the project
        user_id: the id of the current logged-in user; the project's admin

    Raises:
        401: not logged in
        403: the user does not administer the project, or it is their personal project
        404: the project does not exist
    """
    try:
        project = await auth.get_project(database, _id)
    except auth.ProjectNotExists as exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exp

    if user_id != project.admin_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # the service refuses a personal project unless the caller is a superuser
    await auth.delete_project(database, project)
    return None
