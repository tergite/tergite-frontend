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
"""Claims the backends' websocket nonces, so that none is replayed"""

from datetime import timedelta

from libs.storage import Database, DuplicateKeyError
from utils.date_time import get_utc_now

from .dtos import BccNonce


async def claim_bcc_nonce(
    database: Database, device_name: str, nonce: str, ttl: float
) -> bool:
    """Claims the nonce a backend signed its websocket handshake with, so that the handshake
    cannot be replayed

    A nonce is kept for ttl seconds, past which the timestamp the backend signed with it is
    refused as too old anyway.

    Args:
        database: the database the nonces are kept in
        device_name: the name of the backend that opened the websocket
        nonce: the handshake's `x-request-id`
        ttl: the seconds to keep the nonce for, `bcc_nonce_ttl`

    Returns:
        whether the nonce was new; False if another handshake claimed it first
    """
    record = BccNonce(
        nonce=nonce,
        device_name=device_name,
        expires_at=get_utc_now() + timedelta(seconds=ttl),
    )
    try:
        await database.insert(BccNonce, record)
        return True
    except DuplicateKeyError:
        return False
