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
"""Data Transfer Objects for the projects submodule in the auth service"""

from typing import List, Optional, Set

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pymongo import IndexModel

from utils.date_time import get_current_timestamp
from utils.models import create_partial_model

PROJECT_DB_COLLECTION = "auth_projects"
DELETED_PROJECT_DB_COLLECTION = "deleted_auth_projects"


class ProjectBase(BaseModel):
    """The base schema for Project schemas"""

    name: str
    qpu_seconds: float = 0
    description: str = ""


class ProjectCreate(ProjectBase):
    """The schema for creating a project"""

    name: str
    admin_email: str
    user_emails: List[str] = ()


class ProjectRead(ProjectBase):
    """The schema for viewing a project as non admin"""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: PydanticObjectId
    is_active: bool
    user_ids: List[PydanticObjectId]
    admin_id: PydanticObjectId
    is_personal: bool
    created_at: str
    updated_at: str

    def model_dump(self, *args, **kwargs):
        # get rid of the default None's
        return super().model_dump(*args, **{**kwargs, "exclude_none": True})

    @field_serializer("id", "admin_id", when_used="json")
    def serialize_id(self, value: PydanticObjectId):
        """Convert id to string when working with JSON"""
        return str(value)

    @field_serializer("user_ids", when_used="json")
    def serialize_user_ids(self, value: List[PydanticObjectId]):
        """Convert list of ids to list of strings when working with JSON"""
        return [str(v) for v in value]


class ProjectAdminView(ProjectRead):
    """The schema for viewing a project as an admin"""

    model_config = ConfigDict(from_attributes=True)

    admin_email: str
    user_emails: List[str] = ()


class ProjectUpdate(ProjectCreate):
    """The schema for updating a project"""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    admin_email: Optional[str] = None
    user_emails: Optional[List[str]] = None
    qpu_seconds: Optional[float] = None
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)


class Project(ProjectRead, Document):
    model_config = ConfigDict(extra="ignore")

    # optional like any document's, or no project could be made before inserting it
    id: Optional[PydanticObjectId] = None
    is_active: bool = True
    user_ids: List[PydanticObjectId] = ()
    is_personal: bool = False
    created_at: str = Field(default_factory=get_current_timestamp)
    updated_at: str = Field(default_factory=get_current_timestamp)

    class Settings:
        name = PROJECT_DB_COLLECTION
        indexes = [
            IndexModel("name", unique=True),
        ]

    @property
    def members(self) -> Set[PydanticObjectId]:
        """All IDs of the users who are members of the project"""
        return {self.admin_id, *(self.user_ids or [])}


class DeletedProject(Project):
    """The schema of all deleted projects"""

    class Settings:
        name = DELETED_PROJECT_DB_COLLECTION


ProjectPartial = create_partial_model("ProjectPartial", Project, exclude=("id",))
"""The partial project to be used when updating the database"""
