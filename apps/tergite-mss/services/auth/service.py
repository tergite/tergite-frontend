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

"""The auth service's startup, and what it tells about users"""
import re
from typing import List, Optional

from libs.storage import Database
from utils.config import AuthConfig, UserRole

from . import providers
from .users.dtos import Role, User


async def on_startup(database: Database, conf: AuthConfig) -> None:
    """Runs init operations when the application is starting up

    Args:
        database: the database where the users and their roles are kept
        conf: the auth configuration, whose clients are the auth providers listed
    """
    providers.set_auth_providers(conf.clients)
    await ensure_roles(database)


async def ensure_roles(database: Database) -> None:
    """Stores every role users may hold, so that their roles can reference it"""
    for role in UserRole:
        await database.update_one(
            Role, {"name": role}, {"$set": {"name": role}}, should_upsert=True
        )


async def get_user_emails(
    database: Database, search: Optional[str] = None, limit: int = 20
) -> List[str]:
    """Gets user email addresses, alphabetically

    Returns addresses alone, never the user records: the callers that may see this
    are completing a form, not reading a directory.

    Args:
        database: the database where the users are kept
        search: a case-insensitive substring of the address; omit for the first page
        limit: the maximum number of addresses to return

    Returns:
        the matched email addresses
    """
    user_filter = {}
    if search:
        user_filter["email"] = {"$regex": re.escape(search), "$options": "i"}

    users = await database.find(User, filter=user_filter, sort=["email"], limit=limit)
    return [user.email for user in users]
