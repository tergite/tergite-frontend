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
    UserDatabase,
    get_user_db,
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
from .utils import get_request_id

CurrentUserDep = Annotated[User, Depends(GET_CURRENT_USER)]
CurrentSuperuserDep = Annotated[User, Depends(GET_CURRENT_SUPERUSER)]
CurrentUserIdDep = Annotated[str, Depends(GET_CURRENT_USER_ID)]
UserDbDep = Annotated[UserDatabase, Depends(get_user_db)]
CurrentLaxOwnerDep = Annotated[TokenOwner, Depends(get_current_lax_owner)]
CurrentStrictProjectUserIdsDep = Annotated[
    Tuple[str, str], Depends(get_current_project_user_ids)
]
DatabaseDep = Annotated[Database, Depends(get_database)]
BccClientDep = Annotated[bcc.BccClient, Depends(bcc.get_client)]
RequestIdDep = Annotated[str, Depends(get_request_id)]


def get_project_query(
    ids: Optional[List[Id]] = Query(None, alias="id"),
    user_ids: Optional[List[Id]] = Query(None),
    name: Optional[List[str]] = Query(None),
    is_active: Optional[bool] = Query(None),
    min_qpu_seconds: Optional[int] = Query(None),
    max_qpu_seconds: Optional[int] = Query(None),
) -> ProjectQuery:
    """Dependency injector of the query params that narrow a list of projects"""
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
    """Dependency injector of the query params that narrow a list of app tokens"""
    return AppTokenQuery(
        ids=ids,
        project_ids=project_id,
        titles=title,
        min_lifespan_seconds=min_lifespan_seconds,
        max_lifespan_seconds=max_lifespan_seconds,
    )


AppTokenQueryDep = Annotated[AppTokenQuery, Depends(get_app_token_query)]
