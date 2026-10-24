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
"""What the app tokens' authenticator and routes need of projects, until step 5.3"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

from beanie import PydanticObjectId
from fastapi_users.exceptions import UserNotExists
from fastapi_users.types import DependencyCallable

from libs.storage import Database
from utils.exc import TooManyListQueryParams

from ..app_tokens.database import AppTokenDatabase
from ..app_tokens.dtos import AppToken, AppTokenCreate
from ..users.database import UserDatabase
from ..users.dtos import User
from ..utils import MAX_LIST_QUERY_LEN
from . import exc
from . import service as projects_service
from .dtos import Project


class ProjectAppTokenManager:
    """Finds the projects and app tokens that app-token authentication works with"""

    def __init__(
        self,
        database: Database,
        app_token_db: AppTokenDatabase,
        user_db: UserDatabase,
    ):
        self.database = database
        self.app_token_db = app_token_db
        self.user_db = user_db

    async def get_project_user_pair(
        self, project_id: str, user_id: str
    ) -> Tuple[Project, User]:
        """Gets the project of the given id and the user, who must be a member

        Raises:
            ProjectNotExists: the project does not exist or the user is not a member
            UserNotExists: the user does not exist
        """
        user = await self.user_db.get(PydanticObjectId(user_id))
        if user is None:
            raise UserNotExists()

        project = await projects_service.get_project_if_member(
            self.database, str(project_id), str(user_id)
        )
        if project is None:
            raise exc.ProjectNotExists()

        return project, user

    async def find_app_tokens(
        self,
        user_id: str,
        ids: Optional[Sequence[str]] = None,
        project_ids: Optional[Sequence[str]] = None,
        titles: Optional[Sequence[str]] = None,
        min_lifespan_seconds: Optional[float] = None,
        max_lifespan_seconds: Optional[float] = None,
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> List[AppToken]:
        """Finds the user's app tokens that fit the given constraints

        Args:
            user_id: the user whose app tokens are wanted
            ids: the IDs of the app tokens
            project_ids: the IDs of the projects the app tokens are for
            titles: the titles of the app tokens
            min_lifespan_seconds: the shortest lifespan the app tokens have
            max_lifespan_seconds: the longest lifespan the app tokens have
            skip: the number of matched app tokens to skip
            limit: the most app tokens to return; None returns all

        Raises:
            TooManyListQueryParams: a list has more than MAX_LIST_QUERY_LEN items
        """
        token_filter: Dict[str, Any] = {"user_id": user_id}
        if ids is not None:
            token_filter["id"] = {"$in": _ensure_short_list("id", ids)}
        if project_ids is not None:
            token_filter["project_id"] = {
                "$in": _ensure_short_list("project_id", project_ids)
            }
        if titles is not None:
            token_filter["title"] = {"$in": _ensure_short_list("title", titles)}

        lifespan_seconds: Dict[str, float] = {}
        if min_lifespan_seconds is not None:
            lifespan_seconds["$gte"] = min_lifespan_seconds
        if max_lifespan_seconds is not None:
            lifespan_seconds["$lte"] = max_lifespan_seconds
        if lifespan_seconds:
            token_filter["lifespan_seconds"] = lifespan_seconds

        return await self.app_token_db.get_many(token_filter, skip=skip, limit=limit)

    async def authenticate(
        self,
        details: AppTokenCreate,
        user_id: str,
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


def _ensure_short_list(query_param: str, values: Sequence[Any]) -> List[Any]:
    """Gets the values as a list, if there are few enough to query by

    Raises:
        TooManyListQueryParams: there are more than MAX_LIST_QUERY_LEN values
    """
    if len(values) > MAX_LIST_QUERY_LEN:
        raise TooManyListQueryParams(
            query_param, expected=MAX_LIST_QUERY_LEN, got=len(values)
        )
    return list(values)
