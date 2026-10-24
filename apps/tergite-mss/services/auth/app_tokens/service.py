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
from typing import Sequence

from libs.storage import Database

from .dtos import AppToken


async def delete_project_tokens(database: Database, project_id: str) -> int:
    """Deletes every app token for the project, returning how many were deleted"""
    return await database.delete_many(AppToken, {"project_id": project_id})


async def delete_non_member_tokens(
    database: Database, project_id: str, member_ids: Sequence[str]
) -> int:
    """Deletes the project's app tokens of users who are not among its members"""
    return await database.delete_many(
        AppToken, {"project_id": project_id, "user_id": {"$nin": list(member_ids)}}
    )
