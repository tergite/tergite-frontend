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

from beanie import PydanticObjectId
from fastapi import APIRouter, Query

from services import notices as notices_service
from services.auth import (
    APP_TOKEN_AUTH,
    User,
    get_user_emails,
)
from services.external.bcc.dtos import BCCUserProfile, NewBCCUserInfo, RecalibrationInfo
from services.notices.dtos import CustomNoticeCreate, Notice
from utils.api import GeneralMessage, PaginatedListResponse

from ..dependencies import (
    BccClientDep,
    CurrentSuperuserDep,
    CurrentUserDep,
    MongoDbDep,
    RequestIdDep,
)

# TODO: Move the different components into differnet modules and convert this to an admin package

router = APIRouter(prefix="/admin")

router.include_router(
    APP_TOKEN_AUTH.get_projects_router(),
    prefix="/projects",
    tags=["projects"],
)


@router.get("/user-emails/", tags=["users"], dependencies=[CurrentSuperuserDep])
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
    return await get_user_emails(search=search, limit=limit)


@router.post("/bcc-users/{backend}", response_model=BCCUserProfile)
async def create_bcc_user(
    bcc_client: BccClientDep,
    data: NewBCCUserInfo,
    request_id: RequestIdDep,
    requester: User = CurrentUserDep,
) -> dict:
    """Creates a user in the given backend for info

    Only MSS admin users can create users here

    Args:
        data: the information about the new user
        bcc_client: the BCC client for the given backend
        request_id: the unique identifier of the request
        requester: the admin user requesting this operation

    Returns:
        the created user

    Raises:
        UnknownBccError: Unknown backend '{backend}'
    """
    return await bcc_client.create_user(
        user_id=requester.id,
        request_id=request_id,
        data=data,
        is_admin=requester.is_superuser,
    )


@router.delete("/bcc-users/{backend}/{user_id}")
async def remove_bcc_user(
    bcc_client: BccClientDep,
    user_id: str,
    request_id: RequestIdDep,
    requester: User = CurrentUserDep,
) -> GeneralMessage:
    """Deletes the user of the given user_id

    Only admins are allowed to remove users

    Args:
        user_id: the unique identifier of the user
        bcc_client: the BCC client for the given backend
        request_id: the unique identifier of the request
        requester: the admin user requesting this operation

    Raises:
        ItemNotFoundError: user not found
        UnknownBccError: Unknown backend '{backend}'

    Returns:
        A general message object with status
    """
    response = await bcc_client.delete_user(
        bcc_user_id=user_id,
        user_id=requester.id,
        request_id=request_id,
        is_admin=requester.is_superuser,
    )
    return response


@router.get(
    "/bcc-users/{backend}/", response_model=PaginatedListResponse[BCCUserProfile]
)
async def view_bcc_users(
    bcc_client: BccClientDep,
    request_id: RequestIdDep,
    skip: int = Query(default=0),
    limit: Optional[int] = Query(default=None),
    requester: User = CurrentUserDep,
):
    """Views all users

    Only MSS admin users can view this

    Args:
        bcc_client: the BCC client for the given backend
        request_id: the unique identifier of the request
        skip: number of records to ignore at the top of the returned results; default is 0
        limit: maximum number of records to return; default is None.
        requester: the admin user requesting this operation

    Returns:
        the paginated list of the available bookings

    Raises:
        UnknownBccError: Unknown backend '{backend}'
    """
    return await bcc_client.view_users(
        user_id=requester.id,
        request_id=request_id,
        skip=skip,
        limit=limit,
        is_admin=requester.is_superuser,
    )


@router.post("/recalibration/{backend}/init")
async def initialize_recalibration(
    bcc_client: BccClientDep,
    request_id: RequestIdDep,
    start_timestamp: Optional[datetime] = Query(None),
    interval: Optional[float] = Query(None),
    requester: User = CurrentSuperuserDep,
) -> GeneralMessage:
    """Initializes recalibration of the given backend

    Only MSS admin users can initialize recalibration

    Args:
        bcc_client: the BCC client for the given backend
        request_id: the unique identifier of the request
        start_timestamp: the start time of the recalibration; default = None i.e. straight away
        interval: the recalibration interval; default = None i.e. no repeat
        requester: the admin user requesting this operation

    Returns:
        the status of the recalibration
    """
    response = await bcc_client.init_recalibration(
        user_id=requester.id,
        request_id=request_id,
        start_timestamp=start_timestamp,
        interval=interval,
        is_admin=requester.is_superuser,
    )
    return response


@router.get("/recalibration/{backend}/info")
async def get_recalibration_info(
    bcc_client: BccClientDep,
    request_id: RequestIdDep,
    requester: User = CurrentSuperuserDep,
) -> RecalibrationInfo:
    """Gets the current information about the recalibration of the given backend

    Only MSS admin users can get recalibration info

    Args:
        bcc_client: the BCC client for the given backend
        request_id: the unique identifier of the request
        requester: the admin user requesting this operation

    Returns:
        the information about the recalibration
    """
    response = await bcc_client.get_recalibration_info(
        user_id=requester.id,
        request_id=request_id,
        is_admin=requester.is_superuser,
    )
    return response


@router.post("/recalibration/{backend}/cancel")
async def cancel_recalibration(
    bcc_client: BccClientDep,
    request_id: RequestIdDep,
    ignore_errors: bool = Query(False),
    requester: User = CurrentSuperuserDep,
) -> GeneralMessage:
    """Cancels recalibration on this device

    Only MSS admin users can cancel recalibration

    Args:
        bcc_client: the BCC client for the given backend
        request_id: the unique identifier of the request
        ignore_errors: whether to ignore errors during recalibration
        requester: the admin user requesting this operation

    Returns:
        general information on the status of the request
    """
    response = await bcc_client.stop_recalibration(
        user_id=requester.id,
        request_id=request_id,
        is_admin=requester.is_superuser,
        ignore_errors=ignore_errors,
    )
    return response


@router.post("/switch/{backend}/off")
async def switch_backend_off(
    bcc_client: BccClientDep,
    request_id: RequestIdDep,
    requester: User = CurrentSuperuserDep,
) -> GeneralMessage:
    """Switches off the backend

    Only MSS admin users can switch off the device

    Args:
        bcc_client: the BCC client for the given backend
        request_id: the unique identifier of the request
        requester: the admin user requesting this operation

    Returns:
        general information on the status of the request
    """
    response = await bcc_client.switch_off(
        user_id=requester.id,
        request_id=request_id,
        is_admin=requester.is_superuser,
    )
    return response


@router.post("/switch/{backend}/on")
async def switch_backend_on(
    bcc_client: BccClientDep,
    request_id: RequestIdDep,
    requester: User = CurrentSuperuserDep,
) -> GeneralMessage:
    """Switches on the backend

    Only MSS admin users can switch off the device

    Args:
        bcc_client: the BCC client for the given backend
        request_id: the unique identifier of the request
        requester: the admin user requesting this operation

    Returns:
        general information on the status of the request
    """
    response = await bcc_client.switch_on(
        user_id=requester.id,
        request_id=request_id,
        is_admin=requester.is_superuser,
    )
    return response


@router.post("/notices/", response_model_by_alias=False)
async def publish_notice(
    db: MongoDbDep,
    payload: CustomNoticeCreate,
    current_user: User = CurrentSuperuserDep,
) -> Notice:
    """Publishes a notice

    Only MSS admin users can publish notices

    Args:
        db: the MongoDB database where the notice will be stored
        payload: the notice payload
        current_user: the current user

    Returns:
        the created notice
    """
    return await notices_service.publish_custom_notice(
        db, current_user_id=current_user.id, payload=payload
    )


@router.delete(
    "/notices/{notice_id}",
    dependencies=[CurrentSuperuserDep],
    response_model_by_alias=False,
)
async def delete_notice(
    db: MongoDbDep,
    notice_id: PydanticObjectId,
) -> Notice:
    """Deletes a notice

    Only MSS admin users can delete notices

    Args:
        db: the MongoDB database where the notice will be stored
        notice_id: the unique identifier of the notice

    Returns:
        the deleted notice
    """
    return await notices_service.delete_notice(db, pk=notice_id)


@router.get(
    "/notices", response_model_by_alias=False, dependencies=[CurrentSuperuserDep]
)
async def get_many_notices(
    db: MongoDbDep,
    skip: int = 0,
    limit: Optional[int] = None,
    sort: List[str] = Query(("starts_at",)),
    user_id: PydanticObjectId = Query(
        None, description="User ID whose notice count is requested"
    ),
    min_start_utc: datetime = Query(None),
    max_start_utc: datetime = Query(None),
    min_expires_utc: datetime = Query(None),
    max_expires_utc: datetime = Query(None),
    include_dismissed: bool = Query(False),
) -> PaginatedListResponse[Notice]:
    """Gets many notices, filtering them accordingly

    Args:
        db: the MongoDB database where the notice will be stored
        skip: the number of notices to skip
        limit: the maximum number of notices to return
        sort: the sort order
        user_id: The IDs of the users to retrieve notices for
        min_start_utc: The minimum UTC timestamp the notice should start
        max_start_utc: The maximum UTC timestamp the notice should start
        min_expires_utc: The minimum UTC timestamp the notice should expire
        max_expires_utc: The maximum UTC timestamp the notice should expire
        include_dismissed: whether to include dismissed notices; defaults to False

    Returns:
        a paginated list of notices
    """
    data = await notices_service.find_many(
        db,
        limit=limit,
        skip=skip,
        sort=sort,
        user_id=user_id,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        min_expires_utc=min_expires_utc,
        max_expires_utc=max_expires_utc,
        include_dismissed=include_dismissed,
    )
    return PaginatedListResponse(skip=skip, limit=limit, data=data)
