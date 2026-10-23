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

"""Routes for BCC users related operations"""
from typing import Optional

from fastapi import APIRouter, Query

from services.auth import User
from services.external.bcc import BCCUserProfile, NewBCCUserInfo
from utils.api import GeneralMessage, PaginatedListResponse

from ....dependencies import (
    BccClientDep,
    CurrentSuperuserDep,
    RequestIdDep,
)

router = APIRouter()


@router.post("/{backend}", response_model=BCCUserProfile)
async def create_bcc_user(
    bcc_client: BccClientDep,
    data: NewBCCUserInfo,
    request_id: RequestIdDep,
    requester: User = CurrentSuperuserDep,
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


@router.delete("/{backend}/{user_id}")
async def remove_bcc_user(
    bcc_client: BccClientDep,
    user_id: str,
    request_id: RequestIdDep,
    requester: User = CurrentSuperuserDep,
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


@router.get("/{backend}", response_model=PaginatedListResponse[BCCUserProfile])
async def view_bcc_users(
    bcc_client: BccClientDep,
    request_id: RequestIdDep,
    skip: int = Query(default=0),
    limit: Optional[int] = Query(default=None),
    requester: User = CurrentSuperuserDep,
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
