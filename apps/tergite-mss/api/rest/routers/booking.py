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
from typing import Optional

from fastapi import APIRouter, Query

from api.rest.dependencies import CurrentUserDep, CurrentUserIdDep
from services.auth import User
from services.external.bcc.dtos import Booking, GeneralMessage, NewBookingInfo
from utils.api import PaginatedListResponse

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("/bookings/{backend}")
async def create_booking(
    backend: str,
    data: NewBookingInfo,
    user_id: str = CurrentUserIdDep,
) -> Booking:
    """Creates a booking for the user of the given token

    Args:
        backend: the device on which to book
        user_id: the current signed-in user
        data: the information about the new booking

    Returns:
        the newly created booking
    """
    raise NotImplementedError("not implemented")


@router.post("/bookings/{backend}/{booking_id}/cancel")
async def cancel_booking(
    backend: str,
    booking_id: str,
    user: User = CurrentUserDep,
) -> GeneralMessage:
    """Cancels a booking of given id for the user of the given token

    Args:
        backend: the name of the device on which the booking is to be done
        booking_id: the unique identifier of the booking to cancel
        user: the current user

    Returns:
        the general message object with the status
    """
    raise NotImplementedError("not implemented")


@router.get("/bookings/{backend}", dependencies=[CurrentUserIdDep])
async def view_bookings(
    backend: str,
    skip: int = Query(default=0),
    limit: Optional[int] = Query(default=None),
) -> PaginatedListResponse[Booking]:
    """Views all available bookings of the given backend

    Args:
        backend: the backend under consideration
        skip: number of records to ignore at the top of the returned results; default is 0
        limit: maximum number of records to return; default is None.

    Returns:
        the paginated list of the available bookings
    """
    raise NotImplementedError("not implemented")
