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
"""Test utilities for datetime"""
from datetime import datetime, timedelta, timezone

from utils import date_time


def is_not_older_than(timestamp_str: str, seconds: int) -> bool:
    """Checks that the timestamp string is not older than the given number of seconds

    Args:
        timestamp_str: the timestamp string
        seconds: the number of seconds that timestamp should not be older than

    Returns:
        True if timestamp str is not older than the given seconds
    """
    return datetime.fromisoformat(timestamp_str) - datetime.now(
        tz=timezone.utc
    ) <= timedelta(seconds=seconds)


def of_this_month(timestamp_str: str) -> str:
    """Returns the timestamp string as one of the current month

    Args:
        timestamp_str: a timestamp string to be converted to current month's timestamp

    Returns:
        the timestamp but as one of the current month's
    """
    now = datetime.now(tz=timezone.utc)
    timestamp = datetime.fromisoformat(timestamp_str)
    timestamp = timestamp.replace(year=now.year, month=now.month)
    return date_time.datetime_to_zulu(timestamp)


def get_timestamp_str(timestamp: datetime) -> str:
    """Converts a timestamp to a string

    Args:
        timestamp: the datetime value

    Returns:
        the timestamp as a string
    """
    return timestamp.isoformat("T", timespec="milliseconds").replace("+00:00", "Z")


def get_current_timestamp_str() -> str:
    """Gets the current timestamp as a Zulu ISO format string

    Returns:
        the timestamp as a Zulu ISO format string
    """
    timestamp = datetime.now(timezone.utc)
    return get_timestamp_str(timestamp)
