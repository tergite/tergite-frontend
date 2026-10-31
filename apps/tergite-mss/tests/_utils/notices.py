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
"""Test utilities for notices"""
from typing import Any, Dict, List

import pymongo.database
from beanie import PydanticObjectId


def get_user_notices(
    db: pymongo.database.Database, user_id: str
) -> List[Dict[str, Any]]:
    """Gets the notices sent to the given user, oldest first

    Args:
        db: the mongo database where the notices are stored
        user_id: the id of the user

    Returns:
        the notices as stored in the database
    """
    return list(
        db["notices"].find({"user_id": PydanticObjectId(user_id)}).sort("created_at")
    )
