# This code is part of Tergite
#
# (C) Copyright Simon Genne, Arvid Holmqvist, Bashar Oumari, Jakob Ristner,
#               Björn Rosengren, and Jakob Wik 2022 (BSc project)
# (C) Copyright Chalmers Next Labs 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException

import settings


def parse_datetime_string(datetime_str: str) -> datetime:
    """
    Validates the given datetime string is a datetime string. Converts RFC3339 to ISO8601.
    """
    try:
        # Check if Z is on the end of the string. Replace with +00:00 to indicate UTC.
        # If Z is not on the end of the string, then it is assumed to be in the local timezone.
        # RFC3339 standard specifies Z appended on the timestring. ISO8601 uses offset from UTC.
        return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
    except:
        raise HTTPException(
            status_code=400, detail=f'"{datetime_str}" is not a valid date.'
        )


def to_datetime(timestamp: str) -> datetime:
    """converts a timestamp of format like 2024-01-10T14:32:05.880079Z to datetime

    Args:
        timestamp: the timestamp string

    Returns:
        the datetime corresponding to the given timestamp string
    """
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def is_in_month(
    month_year: Tuple[int, int],
    timestamp: str,
) -> bool:
    """Checks if the given timestamp is in the given month

    Note that months start at 1 i.e. January = 1, February = 2, ...

    Args:
        month_year: the (month, year) pair
        timestamp: the timestamp string in format like 2024-01-10T14:32:05.880079Z

    Returns:
        True if the timestamp belongs to the same month, False if otherwise
    """
    timestamp_date = to_datetime(timestamp)
    month, year = month_year
    return timestamp_date.month == month and timestamp_date.year == year


def datetime_to_zulu(d: datetime, precision=settings.CONFIG.datetime_precision) -> str:
    """
    Returns the given datetime object in string format with an ending Z.

    Args:
        d: the datetime to convert
        precision: the number of additional terms of the time to include.
            Valid options are 'auto', 'hours', 'minutes', 'seconds', 'milliseconds' and 'microseconds'.
            Default: "auto"
    """
    # FIXME: MongoDB shaves off the nanoseconds automatically.
    #   to make things uniform in tests, we shave them off here also. But it is possible to store
    #   datetimes as int timestamps instead of dates in order to avoid loss of precision
    return (
        d.astimezone(timezone.utc).isoformat(timespec=precision).replace("+00:00", "Z")
    )


def get_current_timestamp(precision=settings.CONFIG.datetime_precision):
    """Returns current time in UTC string but with hours replaced with a Z"""
    return datetime_to_zulu(datetime.now(timezone.utc), precision=precision)


def get_utc_now() -> datetime:
    """Gets the current timestamp in UTC

    Returns:
        datetime of now with UTC timezone
    """
    return datetime.now(timezone.utc)


def get_relative_time(
    days: float = 0,
    seconds: float = 0,
    microseconds: float = 0,
    milliseconds: float = 0,
    minutes: float = 0,
    hours: float = 0,
    weeks: float = 0,
    baseline: Optional[datetime] = None,
) -> datetime:
    """Gets the datetime given number of seconds, microseconds etc. from the baseline in UTC

    Args:
        days: the number of days
        seconds: the number of seconds
        microseconds: the number of microseconds
        milliseconds: the number of milliseconds
        minutes: the number of minutes
        hours: the number of hours
        weeks: the number of weeks
        baseline: the starting point. It defaults to now in UTC

    Returns:
        datetime a given number of seconds, microseconds etc. from the baseline
    """
    if baseline is None:
        baseline = get_utc_now()

    return baseline + timedelta(
        days=days,
        seconds=seconds,
        microseconds=microseconds,
        milliseconds=milliseconds,
        minutes=minutes,
        hours=hours,
        weeks=weeks,
    )


DEFAULT_FROM_DATETIME_STR = datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc).isoformat()
DEFAULT_TO_DATETIME_STR = datetime.now(timezone.utc).isoformat()
