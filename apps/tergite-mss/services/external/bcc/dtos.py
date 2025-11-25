# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Data Transfer Objects for the BCC service"""
from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)


class NewBCCUserInfo(BaseModel):
    """Schema for creating new users"""

    id: str
    name: str
    email: str
    password: str
    is_admin: bool = False


class BCCUserProfile(BaseModel):
    """Schema for a user's profile"""

    id: str
    name: str
    email: str
    is_admin: bool = False


class NewBookingInfo(BaseModel):
    """Schema for creating new bookings"""

    start_utc: datetime
    end_utc: datetime


class Booking(BaseModel):
    """Schema for booking

    Attributes:
        id: the unique identifier of the booking
        user_id: the unique identifier of the user associated with this booking
        start_utc: the timestamp when the booking starts
        end_utc: the timestamp when the booking ends
        backend: the backend/device this booking is for
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    start_utc: datetime
    end_utc: datetime
    total_duration: float
    backend: str

    @model_validator(mode="after")
    def validate_username(self):
        """The full name of the user"""
        if self.user_id and self.username is None:
            raise ValueError("'username' is required when 'user_id' is set")
        return self


class CancellationDetails(BaseModel):
    """Details to do with a given cancellation request"""

    reason: Optional[str] = None


class BookingsConfig(BaseModel):
    """Configurations for the booking service"""

    max_time_slot_length: float
    min_time_slot_length: float
    max_slots_per_day: int
    max_idle_time: int
    backend: str
