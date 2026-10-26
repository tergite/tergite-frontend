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
"""What only SqlStore does: expiry without a TTL index, on each SQL database"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from pydantic import Field
from sqlalchemy import func, select

from libs.storage import Id, Schema, StorageSpec, generate_id
from libs.storage.sql import SqlStore


class _Session(Schema):
    __storage__ = StorageSpec(table="sessions", expires="expires_at")

    id: Id = Field(default_factory=generate_id)
    expires_at: Optional[datetime] = None


@pytest.fixture
async def store(sql_database_url):
    store = SqlStore(sql_database_url, schemas=[_Session], expiry_sweep_seconds=0.1)
    await store.setup()
    yield store
    await store.close()


async def test_an_expired_record_is_not_read_and_then_deleted(store):
    now = datetime.now(timezone.utc)
    expired = _Session(expires_at=now - timedelta(seconds=1))
    current = _Session(expires_at=now + timedelta(hours=1))
    lasting = _Session()
    for session in (expired, current, lasting):
        await store.insert(_Session, session)

    found = await store.find(_Session, {}, (), 0, None)
    await asyncio.sleep(0.3)

    assert [session.id for session in found] == [current.id, lasting.id]
    assert await store.get(_Session, expired.id) is None
    assert await _count_rows(store) == 2


async def _count_rows(store: SqlStore) -> int:
    """Counts the rows around the expiry filter, to see what the sweep deleted"""
    async with store._engine.connect() as conn:
        table = store._metadata.tables["sessions"]
        return await conn.scalar(select(func.count()).select_from(table))
