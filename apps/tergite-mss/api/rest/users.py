# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""The user manager dependency, which gives each user a personal project on login"""
from functools import partial
from typing import AsyncIterator

from fastapi import Depends

import settings
from libs.storage import Database
from services import auth

from .database import get_database


async def get_user_manager(
    user_db: auth.UserDatabase = Depends(auth.get_user_db),
    email_validator: auth.Validator = Depends(auth.get_email_validator),
    database: Database = Depends(get_database),
) -> AsyncIterator[auth.UserManager]:
    """Dependency injector of the user manager, which gives each user a personal project"""
    yield auth.UserManager(
        user_db,
        email_validator=email_validator,
        on_login=partial(
            auth.ensure_personal_project,
            database,
            qpu_seconds=settings.CONFIG.projects.personal_qpu_seconds,
        ),
    )
