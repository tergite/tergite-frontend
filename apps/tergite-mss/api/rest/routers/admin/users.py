# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import List, Optional

from fastapi import APIRouter, Query

from api.rest.dependencies import CurrentSuperuserDep
from services.auth import service as auth_service

router = APIRouter()


@router.get("/emails/", tags=["users"], dependencies=[CurrentSuperuserDep])
async def get_user_emails(
    search: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
) -> List[str]:
    """Gets user email addresses, for completing the admin project forms

    Superuser only, and deliberately so: a superuser already sees every member address
    through ProjectAdminView, whereas a directory of addresses handed to any logged-in
    user would be a disclosure. Returns addresses alone, never the user records.

    Args:
        search: a case-insensitive substring of the address; omit for the first page
        limit: the maximum number of addresses to return

    Returns:
        the matched email addresses, alphabetically
    """
    return await auth_service.get_user_emails(search=search, limit=limit)
