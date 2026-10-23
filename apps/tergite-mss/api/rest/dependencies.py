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
from typing import Optional, Tuple

from fastapi import Depends
from typing_extensions import Annotated

from libs.storage import Database
from services.auth import (
    Project,
    ProjectDatabase,
    User,
    UserDatabase,
    get_project_db,
    get_user_db,
)

# from api.database import get_mongodb
from services.external import bcc

from .auth import (
    GET_CURRENT_LAX_PROJECT_AND_USER,
    GET_CURRENT_PROJECT_USER_IDS,
    GET_CURRENT_SUPERUSER,
    GET_CURRENT_USER,
    GET_CURRENT_USER_ID,
)
from .database import get_database
from .utils import get_request_id

CurrentUserDep = Annotated[User, Depends(GET_CURRENT_USER)]
CurrentSuperuserDep = Annotated[User, Depends(GET_CURRENT_SUPERUSER)]
CurrentUserIdDep = Annotated[str, Depends(GET_CURRENT_USER_ID)]
UserDbDep = Annotated[UserDatabase, Depends(get_user_db)]
CurrentLaxProjectAndUserDep = Annotated[
    Tuple[Project, User], Depends(GET_CURRENT_LAX_PROJECT_AND_USER)
]
CurrentStrictProjectUserIdsDep = Annotated[
    Tuple[Optional[str], Optional[str]], Depends(GET_CURRENT_PROJECT_USER_IDS)
]
ProjectDbDep = Annotated[ProjectDatabase, Depends(get_project_db)]
DatabaseDep = Annotated[Database, Depends(get_database)]
BccClientDep = Annotated[bcc.BccClient, Depends(bcc.get_client)]
RequestIdDep = Annotated[str, Depends(get_request_id)]
