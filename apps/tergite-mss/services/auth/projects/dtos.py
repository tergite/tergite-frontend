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

from pydantic import BaseModel, ConfigDict, Field

from libs.storage import Id, Schema, StorageSpec, generate_id
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

    id: Id
    is_active: bool
    user_ids: List[Id]
    admin_id: Id
    is_personal: bool
    created_at: str
    updated_at: str

    def model_dump(self, *args, **kwargs):
        # get rid of the default None's
        return super().model_dump(*args, **{**kwargs, "exclude_none": True})


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


class Project(ProjectRead, Schema):
    __storage__ = StorageSpec(
        table=PROJECT_DB_COLLECTION, unique=("name",), indexed_lists=("user_ids",)
    )
    model_config = ConfigDict(extra="ignore")

    id: Id = Field(default_factory=generate_id)
    is_active: bool = True
    user_ids: List[Id] = []
    is_personal: bool = False
    created_at: str = Field(default_factory=get_current_timestamp)
    updated_at: str = Field(default_factory=get_current_timestamp)

    @property
    def members(self) -> Set[str]:
        """All IDs of the users who are members of the project"""
        return {self.admin_id, *self.user_ids}


class DeletedProject(Project):
    """The schema of all deleted projects"""

    # no unique name: a name freed by a deletion can be taken and deleted again
    __storage__ = StorageSpec(table=DELETED_PROJECT_DB_COLLECTION)


ProjectPartial = create_partial_model("ProjectPartial", Project, exclude=("id",))
"""The partial project to be used when updating the database"""
