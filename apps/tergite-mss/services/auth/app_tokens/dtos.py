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
from datetime import datetime
from typing import List, Optional

import pymongo
from beanie import Document, PydanticObjectId
from fastapi_users_db_beanie.access_token import BeanieBaseAccessToken
from pydantic import BaseModel, ConfigDict, field_serializer
from pymongo import IndexModel

from utils.date_time import datetime_to_zulu


class AppTokenCreate(BaseModel):
    """The payload passed when generating an app token"""

    title: str
    project_id: PydanticObjectId
    lifespan_seconds: float

    @field_serializer("project_id", when_used="json")
    def serialize_object_id(self, value: PydanticObjectId):
        """Convert object ID to string when working with JSON"""
        return str(value)


class AppTokenRead(AppTokenCreate):
    """The record as seen much later after creation

    It never shows the token string again.
    It also doesn't show the user id
    """

    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
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


class AppToken(BeanieBaseAccessToken, AppTokenCreate, Document):
    """App token stored in the database"""

    class Settings(BeanieBaseAccessToken.Settings):
        name = "auth_app_tokens"
        indexes = BeanieBaseAccessToken.Settings.indexes + [
            IndexModel(
                [("project_id", pymongo.ASCENDING), ("user_id", pymongo.ASCENDING)],
            ),
        ]


class AppTokenListResponse(BaseModel):
    """The response when sending paginated data"""

    skip: int = 0
    limit: Optional[int] = None
    data: List[AppTokenRead] = []
