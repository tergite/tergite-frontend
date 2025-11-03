# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Routes for observing the bookings

These query the BCC on behalf of the user, thus they use the BCC client.
"""
from datetime import datetime
from typing import Optional, Tuple

from fastapi import APIRouter, Query

from api.rest.dependencies import (
    BccClientDep,
    CurrentUserDep,
    CurrentUserIdDep,
    RequestIdDep,
    UserDbDep,
)
from services.auth import User
from services.external.bcc.dtos import (
    Booking,
    BookingsConfig,
    GeneralMessage,
    NewBookingInfo,
)
from utils.api import PaginatedListResponse

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("/{backend}")
async def create_booking(
    bcc_client: BccClientDep,
    user_db: UserDbDep,
    data: NewBookingInfo,
    request_id: RequestIdDep,
    user_id: str = CurrentUserIdDep,
) -> Booking:
    """Creates a booking for the user of the given token

    Args:
        bcc_client: BccClient for the given backend
        user_db: UserDatabase instance for this application
        data: the information about the new booking
        request_id: the unique identifier of the request
        user_id: the ID of the current signed-in user

    Returns:
        the newly created booking

    Raises:
        UnknownBccError: Unknown backend '{backend}'
    """
    return await bcc_client.create_booking(
        user_db=user_db, user_id=user_id, request_id=request_id, data=data
    )


@router.post("/{backend}/{booking_id}/cancel")
async def cancel_booking(
    bcc_client: BccClientDep,
    booking_id: str,
    request_id: RequestIdDep,
    user_id: str = CurrentUserIdDep,
) -> GeneralMessage:
    """Cancels a booking of given id for the user of the given token

    Args:
        bcc_client: BccClient for the given backend
        booking_id: the unique identifier of the booking to cancel
        request_id: the unique identifier of the request
        user_id: the id of the current signed-in user

    Returns:
        the general message object with the status

    Raises:
        UnknownBccError: Unknown backend '{backend}'
    """
    return await bcc_client.cancel_booking(
        user_id=user_id, request_id=request_id, booking_id=booking_id
    )


@router.get(
    "/{backend}",
    response_model=PaginatedListResponse[Booking],
)
async def view_bookings(
    bcc_client: BccClientDep,
    user_db: UserDbDep,
    request_id: RequestIdDep,
    requester: User = CurrentUserDep,
    skip: int = Query(default=0),
    limit: Optional[int] = Query(default=None),
    sort: Tuple[str, ...] = Query(default=()),
    user_id: str = Query(default=None),
    min_start_utc: Optional[datetime] = Query(default=None),
    max_start_utc: Optional[datetime] = Query(default=None),
):
    """Views all available bookings of the given backend

    Args:
        bcc_client: BccClient for the given backend
        user_db: UserDatabase instance for this application
        request_id: the unique identifier of the request
        requester: the current signed-in user
        skip: number of records to ignore at the top of the returned results; default is 0
        limit: maximum number of records to return; default is None.
        sort: fields to sort by; prepending a "-" returns the items in descending order of that field
        user_id: the id of the owner of the bookings
        min_start_utc: the earliest start timestamp to include in the returned results; default is None
        max_start_utc: the latest end timestamp to include in the returned results; default is None

    Returns:
        the paginated list of the available bookings filtered accordingly

    Raises:
        UnknownBccError: Unknown backend '{backend}'
    """
    return await bcc_client.view_bookings(
        user_db=user_db,
        requester_id=requester.id,
        request_id=request_id,
        is_admin=requester.is_superuser,
        skip=skip,
        limit=limit,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        user_id=user_id,
        sort=sort,
    )


@router.get(
    "/{backend}/config",
    response_model=BookingsConfig,
)
async def view_bookings_configs(
    bcc_client: BccClientDep,
    request_id: RequestIdDep,
    requester: User = CurrentUserDep,
):
    """Views bookings configuration for the given backend

    Args:
        bcc_client: BccClient for the given backend
        request_id: the unique identifier of the request
        requester: the current signed-in user

    Returns:
        the dict of configuration values for the booking service of the given backend

    Raises:
        UnknownBccError: Unknown backend '{backend}'
    """
    return await bcc_client.view_bookings_configs(
        user_id=requester.id,
        request_id=request_id,
        is_admin=requester.is_superuser,
    )
