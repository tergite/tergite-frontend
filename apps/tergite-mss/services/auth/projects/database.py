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
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from libs.storage import Database, DuplicateKeyError, Filter, derive_id
from utils.config import ProjectsConfig

from .dtos import DeletedProject, Project
from .exc import ProjectExists

if TYPE_CHECKING:
    from services.auth.users.dtos import User


class ProjectDatabase:
    """Database adapter for accessing projects"""

    def __init__(self, database: Database, conf: ProjectsConfig):
        self.database = database
        self.conf = conf

    async def get(self, pk: str) -> Optional[Project]:
        """Get a single project by id."""
        return await self.database.get(Project, pk)

    async def create_personal_project_if_not_exist(self, user: "User") -> Project:
        """Creates the user's personal project if they do not have one yet.

        Args:
            user: the user whose personal project is required

        Returns:
            the personal project
        """
        user_id = str(user.id)
        project_id = derive_id(user_id, namespace="project")
        existing = await self.get(project_id)
        if existing is not None:
            return existing

        project = Project(
            id=project_id,
            name=f"{user.username} (personal)",
            description=f"{user.username} personal project",
            qpu_seconds=self.conf.personal_qpu_seconds,
            admin_id=user_id,
            user_ids=[user_id],
            is_personal=True,
        )
        try:
            return await self.database.insert(Project, project)
        except DuplicateKeyError:
            return await self.get(project_id)

    async def get_if_member(self, pk: str, user_id: str) -> Optional[Project]:
        """Get a single project by its primary key if the given user is a member else return None

        Args:
            user_id: the id of the given user
            pk: the external id of the project

        Returns:
            the project if it exists and user is a member or None
        """
        return await self.database.find_one(Project, {"id": pk, "user_ids": user_id})

    async def get_many(
        self, project_filter: Filter, skip: int = 0, limit: Optional[int] = None
    ) -> List[Project]:
        """Get the projects that match the filter."""
        return await self.database.find(
            Project, filter=project_filter, skip=skip, limit=limit
        )

    async def create(self, project: Project) -> Project:
        """Create a project.

        Raises:
            ProjectExists: a project of the same name exists
        """
        try:
            return await self.database.insert(Project, project)
        except DuplicateKeyError:
            raise ProjectExists()

    async def update(self, project: Project, update_dict: Dict[str, Any]) -> Project:
        """Update a project."""
        return await self.database.update_one(
            Project, {"id": project.id}, {"$set": update_dict}
        )

    async def delete(self, project: Project) -> None:
        """Delete a project, keeping a copy of it among the deleted projects."""
        await self.database.delete_one(Project, {"id": project.id})
        deleted_project = DeletedProject(
            **project.model_dump(exclude={"created_at", "updated_at"})
        )
        await self.database.insert(DeletedProject, deleted_project)

    async def add_member(self, project_id: str, user_id: str) -> Optional[Project]:
        """Adds the user to the project's members, if not one already"""
        return await self.database.update_one(
            Project, {"id": project_id}, {"$addToSet": {"user_ids": user_id}}
        )

    async def set_admin(self, project_id: str, user_id: str) -> Optional[Project]:
        """Makes the user the project's admin, and a member if not one already"""
        return await self.database.update_one(
            Project,
            {"id": project_id},
            {"$set": {"admin_id": user_id}, "$addToSet": {"user_ids": user_id}},
        )

    async def increment_qpu_seconds(
        self, project_id: Optional[str], qpu_seconds: float
    ) -> Optional[Project]:
        """Increments the QPU seconds of the given project

        Args:
            project_id: the ID of the project; None matches no project
            qpu_seconds: the seconds to increment by

        Returns:
            the updated project, or None if no project matched
        """
        if project_id is None:
            return None
        return await self.database.update_one(
            Project, {"id": project_id}, {"$inc": {"qpu_seconds": qpu_seconds}}
        )
