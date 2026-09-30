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

"""Definition of the FastAPIUsers-inspired Database adapter for projects"""
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

from beanie import PydanticObjectId, UpdateResponse
from beanie.odm.operators.update.general import Inc
from fastapi_users.models import ID
from pymongo.errors import DuplicateKeyError

from utils.config import ProjectsConfig
from utils.crypto import generate_linked_id

from .dtos import Project
from .exc import ProjectExists

if TYPE_CHECKING:
    from services.auth.users.dtos import User


class ProjectDatabase:
    """Database adapter for accessing projects"""

    def __init__(self, conf: ProjectsConfig):
        self.conf = conf

    @staticmethod
    async def get(pk: ID) -> Optional[Project]:
        """Get a single project by id."""
        return await Project.get(pk)

    async def create_personal_project_if_not_exist(self, user: "User") -> Project:
        """Creates the user's personal project if they do not have one yet.

        Args:
            user: the user whose personal project is required

        Returns:
            the personal project
        """
        project_id = generate_linked_id(user.id, namespace="project")
        existing = await Project.get(project_id)
        if existing is not None:
            return existing

        project = Project(
            id=project_id,
            name=f"{user.username} (personal)",
            description=f"{user.username} personal project",
            qpu_seconds=self.conf.personal_qpu_seconds,
            admin_id=user.id,
            user_ids=[user.id],
            is_personal=True,
        )
        try:
            await project.create()
        except DuplicateKeyError:
            return await Project.get(project_id)

        return project

    @staticmethod
    async def get_if_member(
        pk: PydanticObjectId, user_id: PydanticObjectId
    ) -> Optional[Project]:
        """Get a single project by its primary key if the given user is a member else return None

        Args:
            user_id: the id of the given user
            pk: the external id of the project

        Returns:
            the project if it exists and user is a member or None
        """
        return await Project.find_one(Project.id == pk, Project.user_ids == user_id)

    @staticmethod
    async def get_many(
        filter_obj: Mapping[str, Any], skip: int = 0, limit: Optional[int] = None
    ) -> List[Project]:
        """
        Get a list of projects to basing on filter.

        Args:
            filter_obj: the PyMongo-like filter object e.g. `{"user_emails": "john@example.com"}`.
            skip: the number of matched records to skip
            limit: the maximum number of records to return.
                If None, all possible records are returned.

        Returns:
            the list of matched projects
        """
        return await Project.find(
            filter_obj,
            skip=skip,
            limit=limit,
        ).to_list()

    async def create(self, create_dict: Dict[str, Any]) -> Project:
        """Create a project.

        Raises:
            ProjectExists: a project of the same name exists
        """
        project = Project(**create_dict)
        try:
            await project.create()
        except DuplicateKeyError:
            raise ProjectExists()
        return project

    async def update(self, project: Project, update_dict: Dict[str, Any]) -> Project:
        """Update a project."""
        for key, value in update_dict.items():
            setattr(project, key, value)
        await project.save()
        return project

    async def delete(self, project: Project) -> None:
        """Delete a project."""
        await project.delete()

    @staticmethod
    async def increment_qpu_seconds(project_id: PydanticObjectId, qpu_seconds: float):
        """Increments the QPU seconds of the given project

        Args:
            project_id: the ID of the project
            qpu_seconds: the seconds to increment by

        Returns:
            the updated document
        """
        result = Project.find_one(Project.id == project_id).update(
            Inc({Project.qpu_seconds: qpu_seconds}),
            response_type=UpdateResponse.NEW_DOCUMENT,
        )
        return await result
