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
"""App tokens: the tokens a user generates to act on one of their projects"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from libs.storage import Database, Filter
from utils.exc import ForbiddenError

from ..projects import service as projects
from ..users.dtos import User
from ..utils import ensure_short_list
from .dtos import AppToken, AppTokenCreate, AppTokenQuery, TokenOwner
from .exc import AppTokenNotFound


async def create_app_token(
    database: Database, payload: AppTokenCreate, user_id: str
) -> AppToken:
    """Creates an app token for an active project the user is a member of

    Args:
        database: the database where the app tokens and projects are stored
        payload: the app token's title, project and lifespan
        user_id: the user the app token acts for

    Returns:
        the created app token

    Raises:
        ForbiddenError: the project does not exist, is inactive, or the user is not a member
    """
    project = await projects.get_project_if_member(
        database, payload.project_id, user_id
    )
    if project is None or not project.is_active:
        raise ForbiddenError("Forbidden")

    app_token = AppToken(
        **payload.model_dump(), token=secrets.token_urlsafe(), user_id=user_id
    )
    return await database.insert(AppToken, app_token)


async def get_token_owner(database: Database, token: str) -> Optional[TokenOwner]:
    """Gets the project and user an unexpired app token acts for

    Args:
        database: the database where the app tokens, users and projects are stored
        token: the app token string

    Returns:
        the owner, or None if the token, its user or their membership is gone
    """
    app_token = await _find_unexpired_token(database, {"token": token})
    if app_token is None:
        return None

    user = await database.get(User, app_token.user_id)
    project = await projects.get_project_if_member(
        database, app_token.project_id, app_token.user_id
    )
    if user is None or project is None:
        return None
    return TokenOwner(project=project, user=user)


async def find_app_tokens(
    database: Database,
    user_id: str,
    query: AppTokenQuery,
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[AppToken]:
    """Finds the user's app tokens that fit the query

    Args:
        database: the database where the app tokens are stored
        user_id: the user whose app tokens are wanted
        query: the values the app tokens have; its unset fields match anything
        skip: the number of matched app tokens to skip
        limit: the most app tokens to return; None returns all

    Returns:
        the matching app tokens

    Raises:
        TooManyListQueryParams: a list has more than MAX_LIST_QUERY_LEN items
    """
    token_filter: Dict[str, Any] = {"user_id": user_id}
    if query.ids is not None:
        token_filter["id"] = {"$in": ensure_short_list("id", query.ids)}
    if query.project_ids is not None:
        project_ids = ensure_short_list("project_id", query.project_ids)
        token_filter["project_id"] = {"$in": project_ids}
    if query.titles is not None:
        token_filter["title"] = {"$in": ensure_short_list("title", query.titles)}

    lifespan_seconds: Dict[str, float] = {}
    if query.min_lifespan_seconds is not None:
        lifespan_seconds["$gte"] = query.min_lifespan_seconds
    if query.max_lifespan_seconds is not None:
        lifespan_seconds["$lte"] = query.max_lifespan_seconds
    if lifespan_seconds:
        token_filter["lifespan_seconds"] = lifespan_seconds

    return await database.find(AppToken, filter=token_filter, skip=skip, limit=limit)


async def update_app_token_expiry(
    database: Database, token_id: str, user_id: str, expires_at: datetime
) -> Optional[AppToken]:
    """Moves the expiry of the user's unexpired app token

    Args:
        database: the database where the app tokens are stored
        token_id: the id of the app token
        user_id: the user who owns the app token
        expires_at: the new expiry

    Returns:
        the updated app token, or None if the user has no unexpired token of that id
    """
    app_token = await _find_unexpired_token(
        database, {"id": token_id, "user_id": user_id}
    )
    if app_token is None:
        return None

    lifespan_seconds = (expires_at - app_token.created_at).total_seconds()
    return await database.update_one(
        AppToken, {"id": app_token.id}, {"$set": {"lifespan_seconds": lifespan_seconds}}
    )


async def delete_app_token(database: Database, token_id: str, user_id: str) -> None:
    """Deletes the user's app token, expired or not

    Args:
        database: the database where the app tokens are stored
        token_id: the id of the app token
        user_id: the user who owns the app token

    Raises:
        AppTokenNotFound: app token does not exist.
    """
    deleted = await database.delete_one(AppToken, {"id": token_id, "user_id": user_id})
    if deleted is None:
        raise AppTokenNotFound("app token does not exist.")


async def delete_project_tokens(database: Database, project_id: str) -> int:
    """Deletes every app token for the project

    Args:
        database: the database where the app tokens are stored
        project_id: the id of the project

    Returns:
        the number of app tokens deleted
    """
    return await database.delete_many(AppToken, {"project_id": project_id})


async def delete_non_member_tokens(
    database: Database, project_id: str, member_ids: Sequence[str]
) -> int:
    """Deletes the project's app tokens of users who are not among its members

    Args:
        database: the database where the app tokens are stored
        project_id: the id of the project
        member_ids: the ids of the project's members, whose app tokens are kept

    Returns:
        the number of app tokens deleted
    """
    return await database.delete_many(
        AppToken, {"project_id": project_id, "user_id": {"$nin": list(member_ids)}}
    )


async def _find_unexpired_token(
    database: Database, token_filter: Filter
) -> Optional[AppToken]:
    """Finds the first app token to match the filter, deleting it instead if expired"""
    app_token = await database.find_one(AppToken, token_filter)
    if app_token is None:
        return None

    expires_at = app_token.created_at + timedelta(seconds=app_token.lifespan_seconds)
    if expires_at <= datetime.now(timezone.utc):
        await database.delete_one(AppToken, {"id": app_token.id})
        return None
    return app_token
