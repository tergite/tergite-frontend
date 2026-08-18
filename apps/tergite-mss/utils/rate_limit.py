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
"""Fixed-window rate limiting on redis"""
from typing import Optional

from redis import Redis

import settings
from utils.exc import TooManyRequestsError

_HOUR_IN_SECS = 3600
_connection: Optional[Redis] = None


def get_connection() -> Redis:
    """The shared redis connection for rate limit counters"""
    global _connection
    if _connection is None:
        _connection = Redis.from_url(url=f"{settings.CONFIG.database.redis_url}")
    return _connection


def check(key: str, limit: int, window: float = _HOUR_IN_SECS) -> None:
    """Raises if the counter for the given key has already reached the limit.

    Call before the operation being limited, so that tripping the limit reveals
    nothing about the operation's outcome.

    Args:
        key: the counter key, usually scoped by user
        limit: the maximum number of increments allowed within the window
        window: the window length in seconds

    Raises:
        TooManyRequestsError: rate limit exceeded, retry in at most {window} seconds
    """
    count = get_connection().get(_redis_key(key))
    if count is not None and int(count) >= limit:
        raise TooManyRequestsError(
            f"rate limit exceeded, retry in at most {int(window)} seconds"
        )


def increment(key: str, window: float = _HOUR_IN_SECS) -> int:
    """Counts one occurrence against the given key, expiring the window on first use.

    Args:
        key: the counter key, usually scoped by user
        window: the window length in seconds

    Returns:
        the new count within the current window
    """
    redis_key = _redis_key(key)
    conn = get_connection()
    count = conn.incr(redis_key)
    if count == 1:
        conn.expire(redis_key, int(window))
    return count


def reset(key: str) -> None:
    """Clears the counter for the given key"""
    get_connection().delete(_redis_key(key))


def _redis_key(key: str) -> str:
    return f"__ratelimit__{key}"
