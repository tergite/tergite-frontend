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
"""FastAPIUsers-specific definition of AppTokens Strategy"""
import secrets
from typing import Optional, Tuple

from beanie import PydanticObjectId
from fastapi_users.authentication.strategy import DatabaseStrategy

from .. import AppTokenRead
from ..projects.dtos import Project
from ..projects.exc import ProjectNotExists
from ..projects.manager import ProjectAppTokenManager
from ..users.dtos import User
from .database import AppTokenDatabase
from .dtos import AppTokenCreate, AppTokenUpdate


class AppTokenStrategy(DatabaseStrategy):
    """Strategy that handles app tokens"""

    database: AppTokenDatabase

    def __init__(self, database: AppTokenDatabase):
        super().__init__(database)

    async def write_token(
        self, payload: AppTokenCreate, user_id: PydanticObjectId
    ) -> str:
        token_dict = payload.model_dump()
        token_dict["token"] = secrets.token_urlsafe()
        token_dict["user_id"] = user_id
        access_token = await self.database.create(token_dict)
        return access_token.token

    async def destroy_token(
        self, _id: PydanticObjectId, user_id: PydanticObjectId, **filters
    ) -> None:
        """Destroys the token of the given ID

        Args:
            _id: the ID of the token to destroy
            user_id: the id of the user this token should belong to
            filters: other key-value filters to identify the token

        Raises:
            HTTPException: Forbidden 403 if token is not user's
                or token does not exist or is expired already
        """
        filters.update({"user_id": user_id, "_id": _id})
        return await self.database.delete_one(filters)

    async def read_token(
        self, token: Optional[str], project_manager: ProjectAppTokenManager
    ) -> Optional[Tuple[Project, User]]:
        if token is None:
            return None

        access_token = await self.database.get_by_token(
            token,
        )
        if access_token is None:
            return None

        try:
            user_id = access_token.user_id
            project_id = access_token.project_id
            return await project_manager.get_project_user_pair(
                project_id=project_id, user_id=user_id
            )
        except ProjectNotExists:
            return None

    async def update_token(
        self,
        token_id: PydanticObjectId,
        user_id: PydanticObjectId,
        payload: AppTokenUpdate,
    ) -> Optional[AppTokenRead]:
        return await self.database.update(
            token_id, filters=dict(user_id=user_id), payload=payload
        )
