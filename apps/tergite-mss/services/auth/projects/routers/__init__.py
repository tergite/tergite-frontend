# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
# (C) Copyright Chalmers Next Labs 2026
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
from typing import List, Optional, Type

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from fastapi_users import exceptions, schemas

from services import notices
from services.notices import NoticeType
from utils.api import PaginatedListResponse

from ....notices.dtos import ProjectRequestContext, RefType
from ...users.dtos import CurrentSuperUserDependency, CurrentUserIdDependency, User
from ...users.manager import UserManager, UserManagerDependency
from .. import exc
from ..dtos import (
    Project,
    ProjectAdminView,
    ProjectCreate,
    ProjectPartial,
    ProjectRead,
    ProjectUpdate,
)
from ..manager import ProjectAppTokenManager, ProjectManagerDependency
from . import handlers
from .utils import (
    get_full_admin_project,
    get_projects_filter,
    notify_membership_change,
    prepare_partial_project,
)


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
        responses={200: {"model": PaginatedListResponse[project_schema]}},
    )
    async def get_projects(
        user_id: str = Depends(get_current_user_id),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
        skip: int = Query(0),
        limit: Optional[int] = Query(None),
        ids: Optional[List[PydanticObjectId]] = Query(None, alias="id"),
        user_ids: Optional[List[PydanticObjectId]] = Query(None),
        name: Optional[List[str]] = Query(None),
        is_active: Optional[bool] = Query(None),
        min_qpu_seconds: Optional[int] = Query(None),
        max_qpu_seconds: Optional[int] = Query(None),
    ):
        query_filter = get_projects_filter(
            ids=ids,
            user_ids=user_ids,
            name=name,
            is_active=is_active,
            min_qpu_seconds=min_qpu_seconds,
            max_qpu_seconds=max_qpu_seconds,
        )
        # in an $and, so that a user_ids query narrows the user's projects
        filter_obj = {"$and": [{"user_ids": PydanticObjectId(user_id)}, query_filter]}
        projects = await project_manager.get_many(
            filter_obj=filter_obj,
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
        responses={200: {"model": project_schema}},
    )
    async def get_project(
        id: str,
        user_id: str = Depends(get_current_user_id),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ):
        try:
            parsed_id = project_manager.parse_id(id)
            project = await project_manager.get(parsed_id)
        except (exc.ProjectNotExists, exceptions.InvalidID) as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from e

        if PydanticObjectId(user_id) not in project.members:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="the project does not exist.",
            )

        return schemas.model_validate(project_schema, project).model_dump(mode="json")

    @router.delete(
        "/{_id}/members/{member_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        name="projects:remove_project_member",
    )
    async def remove_member(
        _id: PydanticObjectId,
        member_id: PydanticObjectId,
        user_id: str = Depends(get_current_user_id),
        user_manager: UserManager = Depends(get_user_manager),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ):
        """Removes a member from a project the caller administers.

        Goes through the project manager rather than a raw $pull, so that
        on_before_update revokes the removed member's app tokens for this project.
        """
        try:
            project = await project_manager.get(project_manager.parse_id(_id))
        except (exc.ProjectNotExists, exceptions.InvalidID) as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from e

        current_user = await user_manager.get(PydanticObjectId(user_id))
        if project.admin_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        if member_id == project.admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="the project admin cannot be removed",
            )

        new_user_ids = [v for v in project.user_ids if v != member_id]
        if len(new_user_ids) == len(project.user_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="user not a member"
            )

        await project_manager.update(
            ProjectPartial(user_ids=new_user_ids), project, safe=False
        )

        await notices.create_system_notice(
            user_ids=[member_id],
            notice_type=NoticeType.PROJECT_MEMBERSHIP_REVOKED.id,
            context=ProjectRequestContext(
                project_id=str(project.id),
                project_name=project.name,
                approver_name=current_user.username,
            ),
            ref_type=RefType.PROJECT,
            ref_id=project.id,
        )
        return None

    # route to destroy tokens
    @router.delete(
        "/{_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        name=f"projects:destroy_my_administered_project",
    )
    async def destroy(
        _id: PydanticObjectId,
        user_id: str = Depends(get_current_user_id),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ):
        try:
            parsed_id = project_manager.parse_id(_id)
            project = await project_manager.get(parsed_id)
        except (exc.ProjectNotExists, exceptions.InvalidID) as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from e

        if PydanticObjectId(user_id) != project.admin_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        # the manager refuses a personal project unless the caller is a superuser
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
        status_code=status.HTTP_201_CREATED,
        name="projects:create_project",
    )
    async def create(
        project_create: project_create_schema,  # type: ignore
        actor: User = Depends(get_current_superuser),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ):
        try:
            created_project = await handlers.create_project(
                project_create, project_manager=project_manager, actor=actor
            )
        except exc.ProjectExists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.ExtendedErrorCode.PROJECT_ALREADY_EXISTS,
            )

        return await get_full_admin_project(created_project)

    @router.get(
        "/{id}",
        dependencies=[Depends(get_current_superuser)],
        name="projects:single_project",
        responses={
            status.HTTP_200_OK: {"model": ProjectAdminView},
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
        return await get_full_admin_project(project)

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
        user_ids: Optional[List[PydanticObjectId]] = Query(None),
        name: Optional[List[str]] = Query(None),
        is_active: Optional[bool] = Query(None),
        min_qpu_seconds: Optional[int] = Query(None),
        max_qpu_seconds: Optional[int] = Query(None),
    ):
        filter_obj = get_projects_filter(
            ids=ids,
            user_ids=user_ids,
            name=name,
            is_active=is_active,
            min_qpu_seconds=min_qpu_seconds,
            max_qpu_seconds=max_qpu_seconds,
        )
        projects = await project_manager.get_many(
            filter_obj=filter_obj, skip=skip, limit=limit
        )
        data = await asyncio.gather(
            *(get_full_admin_project(project) for project in projects)
        )
        return PaginatedListResponse(data=data, skip=skip, limit=limit)

    @router.put(
        "/{id}",
        response_model=ProjectAdminView,
        response_model_exclude_none=True,
        name="projects:put_project",
    )
    async def update_project(
        project_update: project_update_schema,  # type: ignore
        request: Request,
        actor: User = Depends(get_current_superuser),
        project=Depends(get_project_or_404),
        project_manager: ProjectAppTokenManager = Depends(get_project_manager),
    ):
        before = project.model_copy(deep=True)
        partial_project = await prepare_partial_project(project, project_update)
        updated_project = await project_manager.update(
            partial_project, project, request=request, safe=False
        )
        await notify_membership_change(before, updated_project, actor)
        return await get_full_admin_project(updated_project)

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
        await project_manager.delete(project, request=request, is_superuser=True)
        return None

    return router
