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
from typing import Dict, Optional, Tuple

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing_extensions import Annotated

import settings
from api.rest.utils import get_request_id
from services.auth import Project, ProjectDatabase, User, get_project_db

# from api.database import get_mongodb
from services.auth.service import (
    GET_CURRENT_LAX_PROJECT,
    GET_CURRENT_PROJECT,
    GET_CURRENT_PROJECT_USER_IDS,
    GET_CURRENT_SUPERUSER,
    GET_CURRENT_SYSTEM_USER_PROJECT,
    GET_CURRENT_USER,
    GET_CURRENT_USER_ID,
    GET_USER_DB,
)
from services.auth.users import UserDatabase
from services.external import bcc
from utils.exc import UnknownBccError
from utils.mongodb import get_mongodb


async def get_default_mongodb():
    return get_mongodb(
        url=f"{settings.CONFIG.database.url}", name=settings.CONFIG.database.name
    )


async def get_bcc_client(
    backend: str,
    bcc_clients_map: Dict[str, bcc.BccClient] = Depends(bcc.get_client_map),
) -> bcc.BccClient:
    """Dependency injector to return the BCC client

    Args:
        backend (str): the name of the backend
        bcc_clients_map (BccClientsMap): the map of BCC clients

    Returns:
        bcc.BccClient: the BCC client

    Raises:
        UnknownBccError: Unknown backend '{backend}'
    """
    try:
        return bcc_clients_map[backend]
    except KeyError:
        raise UnknownBccError(f"Unknown backend '{backend}'")


CurrentSystemUserProjectDep = Annotated[User, Depends(GET_CURRENT_SYSTEM_USER_PROJECT)]
CurrentProjectDep = Depends(GET_CURRENT_PROJECT)
CurrentUserDep = Depends(GET_CURRENT_USER)
CurrentSuperuserDep = Depends(GET_CURRENT_SUPERUSER)
CurrentUserIdDep = Depends(GET_CURRENT_USER_ID)
UserDbDep = Annotated[UserDatabase, Depends(GET_USER_DB)]
CurrentLaxProjectDep = Annotated[Optional[Project], Depends(GET_CURRENT_LAX_PROJECT)]
CurrentStrictProjectDep = Annotated[Optional[Project], Depends(GET_CURRENT_PROJECT)]
CurrentStrictProjectUserIds = Annotated[
    Tuple[Optional[str], Optional[str]], Depends(GET_CURRENT_PROJECT_USER_IDS)
]
ProjectDbDep = Annotated[ProjectDatabase, Depends(get_project_db)]
MongoDbDep = Annotated[AsyncIOMotorDatabase, Depends(get_default_mongodb)]
BccClientsMapDep = Annotated[Dict[str, bcc.BccClient], Depends(bcc.get_client_map)]
BccClientDep = Annotated[bcc.BccClient, Depends(get_bcc_client)]
RequestIdDep = Annotated[str, Depends(get_request_id)]
