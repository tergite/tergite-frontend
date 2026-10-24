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
from typing import Optional, Tuple

from fastapi_users.authentication.strategy import DatabaseStrategy

from libs.storage import Database

from ..projects.dtos import Project
from ..users.dtos import User
from . import service


class AppTokenStrategy(DatabaseStrategy):
    """Strategy that reads app tokens, until step 5.3 replaces it with access rules"""

    def __init__(self, database: Database):
        super().__init__(database)

    async def read_token(self, token: Optional[str]) -> Optional[Tuple[Project, User]]:
        if token is None:
            return None

        owner = await service.get_token_owner(self.database, token)
        if owner is None:
            return None
        return owner.project, owner.user
