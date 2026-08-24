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
from typing import Any, Dict, List, Mapping, Optional

from beanie import PydanticObjectId, UpdateResponse
from beanie.odm.operators.find.logical import Or
from beanie.odm.operators.update.array import AddToSet
from beanie.odm.operators.update.general import Inc, Set
from fastapi_users.models import ID

from .dtos import Project


class ProjectDatabase:
    """Database adapter for accessing projects"""

    async def get(self, id: ID) -> Optional[Project]:
        """Get a single project by id."""
        return await Project.get(id)  # type: ignore

    @staticmethod
    async def get_by_ext_id(ext_id: str) -> Optional[Project]:
        """Get a single project by ext_id."""
        return await Project.find_one(Project.ext_id == ext_id)

    @staticmethod
    async def get_by_ext_and_user_email_or_id(
        ext_id: str, user_email: Optional[str] = None, user_id: Optional[str] = None
    ) -> Optional[Project]:
        """Get a single project by ext_id and user_email.

        The user_email must be among the Project's user emails

        Args:
            user_id: the id of the given user
            user_email: the email of the given user
            ext_id: the external id of the project

        Returns:
            the project that matches the filter
        """
        return await Project.find_one(
            Project.ext_id == ext_id,
            Or(Project.user_emails == user_email, Project.user_ids == user_id),
        )

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
        """Create a project."""
        project = Project(**create_dict)
        await project.create()
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
    async def increment_qpu_seconds(project_id: str, qpu_seconds: float):
        """Increments the QPU seconds of the given project

        Adding time also clears the low-QPU latch, so a project that had gone quiet warns
        again once it next runs low; every top-up path goes through here for that reason.
        Spending time must leave the latch alone, or each job would rearm the warning and
        the admin would hear about the same depletion once per job.

        Args:
            project_id: the ID of the project
            qpu_seconds: the seconds to increment by; negative to spend

        Returns:
            the updated document
        """
        updates = [Inc({Project.qpu_seconds: qpu_seconds})]
        if qpu_seconds > 0:
            updates.append(Set({Project.low_qpu_notified_at: None}))

        return await Project.find_one(
            Project.id == PydanticObjectId(project_id)
        ).update(
            *updates,
            response_type=UpdateResponse.NEW_DOCUMENT,
        )

    @staticmethod
    async def add_member(project_id: str, user_id: str, email: str):
        """Adds a user to the given project, by ID and by email

        Args:
            project_id: the ID of the project
            user_id: the ID of the user to add
            email: the email address of the user to add

        Returns:
            the updated document, or None if there is no such project
        """
        _id = PydanticObjectId(project_id)

        # a project created without members stores null, and $addToSet cannot extend
        # null; the null filter keeps this from clobbering a concurrent addition
        for field in (Project.user_ids, Project.user_emails):
            await Project.find_one(
                Project.id == _id, field == None  # noqa: E711
            ).update(Set({field: []}))

        return await Project.find_one(Project.id == _id).update(
            AddToSet({Project.user_ids: user_id, Project.user_emails: email}),
            response_type=UpdateResponse.NEW_DOCUMENT,
        )
