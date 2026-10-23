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

"""Remembers request ids, so that a replayed one can be told apart"""
from datetime import timedelta
from typing import Optional

from libs.storage import Database, DuplicateKeyError
from utils.date_time import get_utc_now

from .dtos import RequestLog


async def record_request(
    database: Database,
    request_id: str,
    ttl: float,
    client_name: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> bool:
    """Records the request id for ttl seconds

    Returns:
        True, or False if the id was recorded already, i.e. the request is a replay
    """
    now = get_utc_now()
    log = RequestLog(
        request_id=request_id,
        client_name=client_name,
        ip_address=ip_address,
        created_at=now,
        expires_at=now + timedelta(seconds=ttl),
    )
    try:
        await database.insert(RequestLog, log)
        return True
    except DuplicateKeyError:
        return False


async def is_request_recorded(database: Database, request_id: str) -> bool:
    return await database.count(RequestLog, filter={"request_id": request_id}) > 0
