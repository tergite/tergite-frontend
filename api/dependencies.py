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
"""Dependencies to be injected"""
from typing import List, Optional, Tuple

from fastapi import Depends, Query
from typing_extensions import Annotated

from libs.storage import Database, Id
from services.auth import (
    AppTokenQuery,
    ProjectQuery,
    TokenOwner,
    User,
)

# from api.database import get_mongodb
from services.external import bcc

from .auth import (
    GET_CURRENT_SUPERUSER,
    GET_CURRENT_USER,
    GET_CURRENT_USER_ID,
    get_current_lax_owner,
    get_current_project_user_ids,
)
from .database import get_database

CurrentUserDep = Annotated[User, Depends(GET_CURRENT_USER)]
CurrentSuperuserDep = Annotated[User, Depends(GET_CURRENT_SUPERUSER)]
CurrentUserIdDep = Annotated[str, Depends(GET_CURRENT_USER_ID)]
CurrentLaxOwnerDep = Annotated[TokenOwner, Depends(get_current_lax_owner)]
CurrentStrictProjectUserIdsDep = Annotated[
    Tuple[str, str], Depends(get_current_project_user_ids)
]
DatabaseDep = Annotated[Database, Depends(get_database)]
BccClientDep = Annotated[bcc.BccClient, Depends(bcc.get_client)]


def get_project_query(
    ids: Optional[List[Id]] = Query(None, alias="id"),
    user_ids: Optional[List[Id]] = Query(None),
    name: Optional[List[str]] = Query(None),
    is_active: Optional[bool] = Query(None),
    min_qpu_seconds: Optional[int] = Query(None),
    max_qpu_seconds: Optional[int] = Query(None),
) -> ProjectQuery:
    """Dependency injector of the query params that narrow a list of projects

    Args:
        ids: the ids, sent as `id`, of the projects to keep
        user_ids: the ids of users; a kept project has at least one of them as a member
        name: the names of the projects to keep
        is_active: whether to keep only active, or only inactive, projects
        min_qpu_seconds: the fewest QPU seconds a kept project may have
        max_qpu_seconds: the most QPU seconds a kept project may have

    Returns:
        the query for the projects
    """
    return ProjectQuery(
        ids=ids,
        user_ids=user_ids,
        names=name,
        is_active=is_active,
        min_qpu_seconds=min_qpu_seconds,
        max_qpu_seconds=max_qpu_seconds,
    )


ProjectQueryDep = Annotated[ProjectQuery, Depends(get_project_query)]


def get_app_token_query(
    ids: Optional[List[Id]] = Query(None, alias="id"),
    project_id: Optional[List[Id]] = Query(None),
    title: Optional[List[str]] = Query(None),
    min_lifespan_seconds: Optional[int] = Query(None),
    max_lifespan_seconds: Optional[int] = Query(None),
) -> AppTokenQuery:
    """Dependency injector of the query params that narrow a list of app tokens

    Args:
        ids: the ids, sent as `id`, of the app tokens to keep
        project_id: the ids of the projects the kept app tokens belong to
        title: the titles of the app tokens to keep
        min_lifespan_seconds: the shortest lifespan, in seconds, of a kept app token
        max_lifespan_seconds: the longest lifespan, in seconds, of a kept app token

    Returns:
        the query for the app tokens
    """
    return AppTokenQuery(
        ids=ids,
        project_ids=project_id,
        titles=title,
        min_lifespan_seconds=min_lifespan_seconds,
        max_lifespan_seconds=max_lifespan_seconds,
    )


AppTokenQueryDep = Annotated[AppTokenQuery, Depends(get_app_token_query)]
