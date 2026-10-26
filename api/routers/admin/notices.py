# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Routes for admin related operations"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query

from libs.storage import Id
from services import notices as notices_service
from services.notices import CustomNoticeCreate, Notice, NoticeQuery, NoticeTypeId
from utils.api import PaginatedListResponse

from ...dependencies import (
    CurrentSuperuserDep,
    DatabaseDep,
)

router = APIRouter()


@router.post("/", response_model_by_alias=False)
async def publish_notice(
    database: DatabaseDep,
    payload: CustomNoticeCreate,
    current_user: CurrentSuperuserDep,
) -> List[Notice]:
    """Publishes a notice

    Only MSS admin users can publish notices

    Args:
        database: the database where the notices are stored
        payload: the notice payload
        current_user: the current user

    Returns:
        the created notices, one per targeted user or a single broadcast notice
    """
    return await notices_service.publish_custom_notice(
        database, current_user_id=current_user.id, payload=payload
    )


@router.delete(
    "/{notice_id}",
    response_model_by_alias=False,
)
async def delete_notice(
    database: DatabaseDep,
    requester: CurrentSuperuserDep,
    notice_id: Id,
) -> Notice:
    """Deletes a notice

    Only MSS admin users can delete notices

    Args:
        database: the database where the notices are stored
        requester: the superuser making the request; anyone else gets a 403
        notice_id: the unique identifier of the notice

    Returns:
        the deleted notice
    """
    return await notices_service.delete_notice(database, pk=notice_id)


@router.get("", response_model_by_alias=False)
async def get_many_notices(
    database: DatabaseDep,
    requester: CurrentSuperuserDep,
    skip: int = 0,
    limit: Optional[int] = None,
    sort: List[str] = Query(("starts_at",)),
    user_id: Id = Query(None, description="User ID whose notice count is requested"),
    min_start_utc: datetime = Query(None),
    max_start_utc: datetime = Query(None),
    min_expires_utc: datetime = Query(None),
    max_expires_utc: datetime = Query(None),
    include_dismissed: bool = Query(False),
    types: List[NoticeTypeId] = Query((), alias="type"),
) -> PaginatedListResponse[Notice]:
    """Gets many notices, filtering them accordingly

    Args:
        database: the database where the notices are stored
        requester: the superuser making the request; anyone else gets a 403
        skip: the number of notices to skip
        limit: the maximum number of notices to return
        sort: the sort order
        user_id: The IDs of the users to retrieve notices for
        min_start_utc: The minimum UTC timestamp the notice should start
        max_start_utc: The maximum UTC timestamp the notice should start
        min_expires_utc: The minimum UTC timestamp the notice should expire
        max_expires_utc: The maximum UTC timestamp the notice should expire
        include_dismissed: whether to include dismissed notices; defaults to False
        types: the types to filter by; repeat the param for many

    Returns:
        a paginated list of notices
    """
    query = NoticeQuery(
        user_id=user_id,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        min_expires_utc=min_expires_utc,
        max_expires_utc=max_expires_utc,
        should_include_dismissed=include_dismissed,
        types=types,
    )
    data = await notices_service.find_many(
        database, query=query, sort=sort, skip=skip, limit=limit
    )
    return PaginatedListResponse(skip=skip, limit=limit, data=data)
