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
"""FastAPIUsers-inspired logic for managing projects"""
from typing import Any, List, Mapping, Optional, Tuple

from beanie import PydanticObjectId
from fastapi.requests import Request
from fastapi_users.exceptions import UserNotExists
from fastapi_users.models import ID
from fastapi_users.types import DependencyCallable
from fastapi_users_db_beanie import ObjectIDIDMixin

from libs.storage import Filter, Page
from utils.exc import ForbiddenError

from ..app_tokens.database import AppTokenDatabase
from ..app_tokens.dtos import AppToken, AppTokenCreate
from ..users.database import UserDatabase
from ..users.dtos import User
from . import exc
from .database import ProjectDatabase
from .dtos import Project, ProjectPartial


class ProjectAppTokenManager(ObjectIDIDMixin):
    """
    Project management logic.

    Attrs:
        project_db: Database adapter instance for projects.
    """

    project_db: ProjectDatabase
    app_token_db: AppTokenDatabase
    user_db: UserDatabase

    def __init__(
        self,
        project_db: ProjectDatabase,
        app_token_db: AppTokenDatabase,
        user_db: UserDatabase,
    ):
        self.project_db = project_db
        self.app_token_db = app_token_db
        self.user_db = user_db

    async def get(self, id: ID) -> Project:
        """
        Get a project by id.

        Args:
            id: ID of the project to retrieve.

        Raises:
            ProjectNotExists: The project does not exist.

        Returns:
            the project.
        """
        project = await self.project_db.get(str(id))

        if project is None:
            raise exc.ProjectNotExists()

        return project

    async def get_project_user_pair(
        self, project_id: str | PydanticObjectId, user_id: str | PydanticObjectId
    ) -> Tuple[Project, User]:
        """
        Get a tuple of project and user for the given by project_id and user_id.

        The user_id must be attached to this project.

        Args:
            project_id: id of the project to retrieve.
            user_id: user_id of the project to retrieve.

        Raises:
            ProjectNotExists: The project does not exist or user_id is not attached to it.
            UserNotExists: the user does not exist

        Returns:
            the project
        """
        user = await self.user_db.get(PydanticObjectId(user_id))

        if user is None:
            raise UserNotExists()

        project = await self.project_db.get_if_member(
            pk=str(project_id), user_id=str(user_id)
        )

        if project is None:
            raise exc.ProjectNotExists()

        return project, user

    async def get_many(self, where: Filter, page: Page = Page()) -> List[Project]:
        """Get the projects that match the filter."""
        return await self.project_db.get_many(where, page=page)

    async def get_many_app_tokens(
        self, filter_obj: Mapping[str, Any], skip: int = 0, limit: Optional[int] = None
    ) -> List[AppToken]:
        """
        Get a list of app tokens to basing on filter.

        Args:
            filter_obj: the PyMongo-like filter object e.g. `{"user_id": "uidufiud"}`.
            skip: the number of matched records to skip
            limit: the maximum number of records to return.
                If None, all possible records are returned.

        Returns:
            the list of matched app tokens
        """
        return await self.app_token_db.get_many(
            filter_obj,
            skip=skip,
            limit=limit,
        )

    async def create(
        self,
        project: Project,
        request: Optional[Request] = None,
        **kwargs,
    ) -> Project:
        """
        Create a project in database.

        Args:
            project: The Project model to create.
            request: Optional FastAPI request that triggered the operation, defaults to None.

        Returns:
            a new project.

        Raises:
            ProjectExists: a project of the same name exists
        """
        return await self.project_db.create(project)

    async def update(
        self,
        project_partial: ProjectPartial,
        project: Project,
        request: Optional[Request] = None,
        **kwargs,
    ) -> Project:
        """Update a project.

        Triggers the on_before_update handler before the update happens
        Triggers the on_after_update handler on success

        Args:
            project_partial: The ProjectPartial model containing
                the changes to apply to the user.
            project: The current user to update.
            request: Optional FastAPI request that
                triggered the operation, defaults to None.

        Returns:
            the updated project.
        """
        await self.on_before_update(project, project_partial)
        update_dict = project_partial.model_dump(exclude_none=True)
        updated_project = await self.project_db.update(project, update_dict)
        return updated_project

    async def delete(
        self,
        project: Project,
        request: Optional[Request] = None,
        is_superuser: bool = False,
    ) -> None:
        """Delete a project.

        Args:
            project: The user to delete.
            request: Optional FastAPI request that
                triggered the operation, defaults to None.
            is_superuser: whether the caller is acting as a superuser; defaults to False
                so a caller that does not say is treated as not.

        Raises:
            ForbiddenError: you cannot delete your own personal project
        """
        if project.is_personal and not is_superuser:
            # a personal project is recreated on next login with a fresh allowance, so
            # its owner deleting it would be an allowance farm. Superusers may, for
            # offboarding and erasure.
            raise ForbiddenError("you cannot delete your own personal project")

        await self.on_before_delete(project, request)
        await self.project_db.delete(project)

    async def on_before_update(
        self, original: Project, new_updates: ProjectPartial
    ) -> None:
        """Perform logic before the project is updated.

        Here, any AppTokens for this project that have user_ids,
        whose associated user emails have been removed, are deleted.

        Args:
            original: the project to be updated
            new_updates: the new updates
        """
        if new_updates.user_ids:
            # app tokens are still Beanie documents, keyed by ObjectIds
            filter_obj = {
                "user_id": {
                    "$nin": [PydanticObjectId(v) for v in new_updates.user_ids]
                },
                "project_id": PydanticObjectId(original.id),
            }
            await self.app_token_db.delete_many(filter_obj)

    async def on_before_delete(
        self, project: Project, request: Optional[Request] = None
    ) -> None:
        """Perform logic before project delete.

        Here, all AppTokens for this project are deleted.

        Args:
            project: the project to be deleted
            request: Optional FastAPI request that triggered the operation
        """
        await self.app_token_db.delete_many(
            {"project_id": PydanticObjectId(project.id)}
        )

    async def authenticate(
        self,
        details: AppTokenCreate,
        user_id: PydanticObjectId,
    ) -> Optional[Project]:
        """
        Authenticate and return a project for the project_id of token and user_id.

        Args:
            details: The app token details to use to generate an app token.
            user_id: the id of the user who is logged in now

        Raises:
            ProjectNotExists: if project does not exist or user does not have access.

        Returns:
            the project of the given project_id in details, and id in current_user
        """
        try:
            project, _ = await self.get_project_user_pair(
                details.project_id, user_id=user_id
            )
            return project
        except exc.ProjectNotExists:
            return None


ProjectManagerDependency = DependencyCallable[ProjectAppTokenManager]
