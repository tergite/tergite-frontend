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

"""A collection of routers for the projects submodule of the auth service"""
import asyncio
from typing import Dict, List, Optional, Type, Union

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from fastapi_users import exceptions, schemas
from fastapi_users.password import PasswordHelper
from pydantic import BaseModel, Field

from utils.api import PaginatedListResponse

from ..users.dtos import CurrentSuperUserDependency, CurrentUserIdDependency, User
from ..users.manager import UserManager, UserManagerDependency
from ..utils import MAX_LIST_QUERY_LEN, TooManyListQueryParams
from . import exc
from .dtos import (
    Project,
    ProjectAdminView,
    ProjectCreate,
    ProjectPartial,
    ProjectRead,
    ProjectUpdate,
)
from .manager import ProjectAppTokenManager, ProjectManagerDependency

_password_helper = PasswordHelper()


def get_my_projects_router(
    get_project_manager: ProjectManagerDependency,
    get_user_manager: UserManagerDependency,
    get_current_user_id: CurrentUserIdDependency,
    project_schema: Type[ProjectRead],
    **kwargs,
) -> APIRouter:
    """Generate a router for viewing my the projects."""
    router = APIRouter()

    @router.get(
        "/",
        name="projects:my_many_projects",
    )
    async def get_projects(
        user_id: str = Depends(get_current_user_id),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
        user_manager: UserManager = Depends(get_user_manager),
        skip: int = Query(0),
        limit: Optional[int] = Query(None),
    ):
        user = await user_manager.get(PydanticObjectId(user_id))
        projects = await project_manager.get_many(
            filter_obj={"$or": [{"user_emails": user.email}, {"user_ids": user_id}]},
            skip=skip,
            limit=limit,
        )

        data = [schemas.model_validate(project_schema, project) for project in projects]
        return PaginatedListResponse(data=data, skip=skip, limit=limit).model_dump(
            mode="json"
        )

    @router.get(
        "/{id}",
        name="projects:my_single_project",
    )
    async def get_project(
        id: str,
        user_id: str = Depends(get_current_user_id),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
        user_manager: UserManager = Depends(get_user_manager),
    ):
        try:
            parsed_id = project_manager.parse_id(id)
            project = await project_manager.get(parsed_id)
        except (exc.ProjectNotExists, exceptions.InvalidID) as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from e

        user = await user_manager.get(PydanticObjectId(user_id))
        user_emails: List[str] = (
            project.user_emails if project.user_emails is not None else []
        )
        user_ids: List[str] = project.user_ids if project.user_ids is not None else []

        if user is None or (
            user.email not in user_emails and str(user.id) not in user_ids
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="the project does not exist.",
            )

        return schemas.model_validate(project_schema, project).model_dump(mode="json")

    # route to destroy tokens
    @router.delete(
        "/{_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        name=f"projects:destroy_my_administered_project",
    )
    async def destroy(
        _id: PydanticObjectId,
        user_id: str = Depends(get_current_user_id),
        user_manager: UserManager = Depends(get_user_manager),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ):
        try:
            parsed_id = project_manager.parse_id(_id)
            project = await project_manager.get(parsed_id)
        except (exc.ProjectNotExists, exceptions.InvalidID) as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from e

        user = await user_manager.get(PydanticObjectId(user_id))

        if user is None or str(user.id) != project.admin_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        await project_manager.delete(project)
        return None

    return router


def get_projects_router(
    get_project_manager: ProjectManagerDependency,
    get_current_superuser: CurrentSuperUserDependency,
    project_update_schema: Type[ProjectUpdate],
    project_create_schema: Type[ProjectCreate],
    **kwargs,
) -> APIRouter:
    """Generate a router with the projects' routes."""
    router = APIRouter()

    async def get_project_or_404(
        id: str,
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ) -> Project:
        try:
            parsed_id = project_manager.parse_id(id)
            return await project_manager.get(parsed_id)
        except (exc.ProjectNotExists, exceptions.InvalidID) as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from e

    @router.post(
        "/",
        response_model=ProjectAdminView,
        response_model_exclude_none=True,
        dependencies=[Depends(get_current_superuser)],
        status_code=status.HTTP_201_CREATED,
        name="projects:create_project",
    )
    async def create(
        project_create: project_create_schema,  # type: ignore
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ):
        try:
            project_create = await _prepare_new_project(project_create)
            created_project = await project_manager.create(project_create)
        except exc.ProjectExists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.ExtendedErrorCode.PROJECT_ALREADY_EXISTS,
            )

        return await _get_full_admin_project(created_project)

    @router.get(
        "/{id}",
        dependencies=[Depends(get_current_superuser)],
        name="projects:single_project",
        responses={
            status.HTTP_401_UNAUTHORIZED: {
                "description": "Missing token or inactive project.",
            },
            status.HTTP_403_FORBIDDEN: {
                "description": "Not a superuser.",
            },
            status.HTTP_404_NOT_FOUND: {
                "description": "The project does not exist.",
            },
        },
    )
    async def get_project(project=Depends(get_project_or_404)):
        return await _get_full_admin_project(project)

    @router.get(
        "/",
        response_model=PaginatedListResponse[ProjectAdminView],
        dependencies=[Depends(get_current_superuser)],
        name="projects:many_projects",
    )
    async def get_many_projects(
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
        skip: int = Query(0),
        limit: Optional[int] = Query(None),
        ids: Optional[List[PydanticObjectId]] = Query(None, alias="id"),
        user_ids: Optional[List[str]] = Query(None),
        ext_id: Optional[List[str]] = Query(None),
        is_active: Optional[bool] = Query(None),
        min_qpu_seconds: Optional[int] = Query(None),
        max_qpu_seconds: Optional[int] = Query(None),
    ):
        filter_obj = {}
        if ids is not None:
            if len(ids) > MAX_LIST_QUERY_LEN:
                raise TooManyListQueryParams(
                    "id", expected=MAX_LIST_QUERY_LEN, got=len(ids)
                )

            filter_obj["_id"] = {"$in": ids}

        if user_ids is not None:
            if len(user_ids) > MAX_LIST_QUERY_LEN:
                raise TooManyListQueryParams(
                    "user_ids", expected=MAX_LIST_QUERY_LEN, got=len(user_ids)
                )

            filter_obj["user_ids"] = {"$in": user_ids}

        if ext_id is not None:
            if len(ext_id) > MAX_LIST_QUERY_LEN:
                raise TooManyListQueryParams(
                    "ext_id", expected=MAX_LIST_QUERY_LEN, got=len(ext_id)
                )

            filter_obj["ext_id"] = {"$in": ext_id}

        if is_active is not None:
            filter_obj["is_active"] = is_active

        if min_qpu_seconds is not None:
            filter_obj["qpu_seconds"] = {"$gte": min_qpu_seconds}

        if max_qpu_seconds is not None:
            if "qpu_seconds" not in filter_obj:
                filter_obj["qpu_seconds"] = {}

            filter_obj["qpu_seconds"].update({"$lte": max_qpu_seconds})

        projects = await project_manager.get_many(
            filter_obj=filter_obj, skip=skip, limit=limit
        )
        data = await asyncio.gather(
            *(_get_full_admin_project(project) for project in projects)
        )
        return PaginatedListResponse(data=data, skip=skip, limit=limit)

    @router.put(
        "/{id}",
        response_model=ProjectAdminView,
        response_model_exclude_none=True,
        dependencies=[Depends(get_current_superuser)],
        name="projects:put_project",
    )
    async def update_project(
        project_update: project_update_schema,  # type: ignore
        request: Request,
        project=Depends(get_project_or_404),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ):
        partial_project = await _prepare_partial_project(project, project_update)
        updated_project = await project_manager.update(
            partial_project, project, request=request, safe=False
        )
        return await _get_full_admin_project(updated_project)

    @router.delete(
        "/{id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        dependencies=[Depends(get_current_superuser)],
        name="projects:delete_project",
    )
    async def delete_project(
        request: Request,
        project=Depends(get_project_or_404),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ):
        await project_manager.delete(project, request=request)
        return None

    return router


async def _prepare_partial_project(
    project: Project, payload: ProjectUpdate
) -> ProjectPartial:
    """Prepares the partial project for updating the project

    It replaces user_emails and admin_email with user ids

    Args:
        project: the project to update
        payload: the payload to convert

    Returns:
        the ProjectPartial instance with proper user_ids and admin_id
    """
    is_user_ids_updating = payload.user_emails is not None
    is_admin_id_updating = payload.admin_email is not None

    user_emails = (payload.user_emails or []) + [payload.admin_email]
    user_emails = [k for k in user_emails if k is not None]
    email_id_map = await _get_user_email_id_map(user_emails)
    user_ids: Optional[List[str]] = None

    admin_id = str(project.admin_id)
    if is_admin_id_updating:
        admin_id = email_id_map[payload.admin_email]

    if is_user_ids_updating:
        user_ids = [email_id_map[email] for email in payload.user_emails]

    if is_user_ids_updating and admin_id not in user_ids:
        user_ids.append(admin_id)

    if not is_user_ids_updating and admin_id not in project.user_ids:
        user_ids = [*project.user_ids, admin_id]

    kwargs = payload.model_dump(exclude={"admin_email", "user_emails"})
    return ProjectPartial(**kwargs, user_ids=user_ids, admin_id=admin_id)


async def _prepare_new_project(payload: ProjectCreate) -> Project:
    """Prepares a new Project instance from a ProjectCreate instance

    Args:
        payload: the payload to convert

    Returns:
        the Project instance
    """
    all_emails = [*payload.user_emails, payload.admin_email]
    email_id_map = await _get_user_email_id_map(all_emails)

    user_ids = [email_id_map[email] for email in payload.user_emails]
    admin_id = email_id_map[payload.admin_email]

    if admin_id not in user_ids:
        user_ids.append(admin_id)

    kwargs = payload.model_dump(exclude={"user_emails", "admin_email"})
    return Project(**kwargs, user_ids=user_ids, admin_id=admin_id)


async def _get_user_email_id_map(user_emails: List[str]) -> Dict[str, str]:
    """Generates a map of user email and their id

    It creates any users for emails whose users don't exist

    Args:
        user_emails: the emails of the users

    Returns:
        the map of the user emails and their corresponding user ids
    """
    if len(user_emails) == 0:
        # return without doing any db requests
        return {}

    users = await User.find({"email": {"$in": user_emails}}).to_list()
    email_id_map = {v.email: str(v.id) for v in users}

    # create any users who don't exist yet
    new_user_ids = []
    new_emails = [email for email in user_emails if email_id_map.get(email) is None]
    new_users = [
        User(
            email=email,
            hashed_password=_password_helper.hash(_password_helper.generate()),
        )
        for email in new_emails
    ]
    if len(new_users) > 0:
        inserted_users = await User.insert_many(new_users, ordered=True)
        new_user_ids = inserted_users.inserted_ids

    # update the email map
    email_id_map.update(
        {email: str(_id) for email, _id in zip(new_emails, new_user_ids)}
    )

    return email_id_map


async def _get_full_admin_project(
    project: Union[ProjectAdminView, Project],
) -> ProjectAdminView:
    """Returns a project admin view with user_emails and admin_email fields filled

    Args:
        project: the admin project to enhance

    Returns:
        the enhanced admin project

    Raises:
        KeyError: user id does not exist in database
    """
    id_email_map = await _get_user_id_email_map([*project.user_ids, project.admin_id])
    props = project.model_dump(exclude={"user_emails", "admin_email"})
    user_emails = [id_email_map[v] for v in project.user_ids]
    admin_email = id_email_map[project.admin_id]
    return ProjectAdminView(**props, user_emails=user_emails, admin_email=admin_email)


class _TrimmedUser(BaseModel):
    """A user object with only email and _id"""

    email: str
    id: PydanticObjectId = Field(alias="_id")


async def _get_user_id_email_map(user_ids: List[str]) -> Dict[str, str]:
    """Gets the user emails for the given user ids as a map

    Args:
        user_ids: the ids of the users in string form

    Returns:
        the map of the user id and email
    """
    parsed_user_ids = [PydanticObjectId(v) for v in user_ids]
    users = await User.find(
        {"_id": {"$in": parsed_user_ids}}, projection_model=_TrimmedUser
    ).to_list()
    return {str(v.id): v.email for v in users}
