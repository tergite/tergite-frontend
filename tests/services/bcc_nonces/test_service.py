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
"""Tests for claiming the backends' websocket nonces"""

from datetime import timedelta

import pytest

from libs.storage import Database
from services.bcc_nonces import BccNonce, claim_bcc_nonce
from utils.date_time import get_utc_now

_TTL = timedelta(seconds=90)
_MILLISECOND = timedelta(milliseconds=1)


@pytest.fixture
async def database(database_url):
    database = Database(database_url, schemas=[BccNonce])
    await database.setup()
    yield database
    await database.close()


async def test_a_nonce_is_claimed_once(database):
    assert await claim_bcc_nonce(database, "Loke", "n-1", ttl=60) is True
    assert await claim_bcc_nonce(database, "Loke", "n-1", ttl=60) is False
    assert await claim_bcc_nonce(database, "Loke", "n-2", ttl=60) is True


async def test_a_nonce_is_kept_for_its_ttl(database):
    before = get_utc_now()
    await claim_bcc_nonce(database, "Loke", "n-1", ttl=90)
    after = get_utc_now()

    nonce = await database.get(BccNonce, "n-1")

    assert nonce.device_name == "Loke"
    # MongoDB keeps milliseconds
    assert before + _TTL - _MILLISECOND <= nonce.expires_at <= after + _TTL
