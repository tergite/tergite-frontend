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
"""Data Transfer Objects for app tokens submodule in the auth service"""
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from libs.storage import Id, Schema, StorageSpec, generate_id
from utils.date_time import datetime_to_zulu

from ..projects.dtos import Project
from ..users.dtos import User


class AppTokenCreate(BaseModel):
    """The payload passed when generating an app token"""

    title: str
    project_id: Id
    lifespan_seconds: float


class AppTokenRead(AppTokenCreate):
    """The record as seen much later after creation

    It never shows the token string again.
    It also doesn't show the user id
    """

    model_config = ConfigDict(from_attributes=True)

    id: Id
    created_at: datetime

    @field_serializer("created_at", when_used="json")
    def serialize_created_at(self, created_at: datetime):
        """Convert created_at to string when working with JSON"""
        return datetime_to_zulu(created_at)


class AppTokenUpdate(BaseModel):
    """The record used to update the app token"""

    expires_at: datetime

    @field_serializer("expires_at", when_used="json")
    def serialize_expires_at(self, expires_at: datetime):
        """Convert expires_at to string when working with JSON"""
        return datetime_to_zulu(expires_at)


class AppToken(AppTokenCreate, Schema):
    """App token stored in the database"""

    __storage__ = StorageSpec(
        table="auth_app_tokens",
        unique=("token",),
        indexes=(("project_id", "user_id"),),
    )

    id: Id = Field(default_factory=generate_id)
    token: str
    user_id: Id
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BearerResponse(BaseModel):
    """A new app token, as a bearer token"""

    access_token: str
    token_type: str


class AppTokenListResponse(BaseModel):
    """The response when sending paginated data"""

    skip: int = 0
    limit: Optional[int] = None
    data: List[AppTokenRead] = []


class AppTokenQuery(BaseModel):
    """The query params that narrow a list of app tokens"""

    ids: Optional[List[Id]] = None
    project_ids: Optional[List[Id]] = None
    titles: Optional[List[str]] = None
    min_lifespan_seconds: Optional[int] = None
    max_lifespan_seconds: Optional[int] = None


class TokenOwner(BaseModel):
    """The project an app token acts on, and the user it acts for"""

    project: Project
    user: User
