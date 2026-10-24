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
"""AppTokenDatabase on each database: tokens by token, owner and project, and expiry"""
from datetime import datetime, timedelta, timezone

import pytest

from libs.storage import Database, DuplicateKeyError, generate_id
from services import auth
from services.auth import AppToken
from services.auth.app_tokens.database import AppTokenDatabase
from services.auth.app_tokens.dtos import AppTokenUpdate
from services.auth.app_tokens.exc import AppTokenNotFound

_USER_ID = generate_id()
_PROJECT_ID = generate_id()


@pytest.fixture
async def token_db(database_url):
    database = Database(database_url, schemas=auth.SCHEMAS)
    await database.setup()
    yield AppTokenDatabase(database)
    await database.close()


async def test_a_token_is_found_by_its_token_and_kept_unique(token_db):
    token = await token_db.create(_get_token())

    assert await token_db.get_by_token("t-1") == token
    with pytest.raises(DuplicateKeyError):
        await token_db.create(_get_token())


async def test_an_expired_token_is_deleted_when_read(token_db):
    await token_db.create(_get_token(lifespan_seconds=0))

    assert await token_db.get_by_token("t-1") is None
    assert await token_db.get_many({}) == []


async def test_a_token_lifespan_is_extended(token_db):
    token = await token_db.create(_get_token())
    expires_at = token.created_at + timedelta(hours=2)

    updated = await token_db.update(
        token.id, _USER_ID, AppTokenUpdate(expires_at=expires_at)
    )

    assert updated.lifespan_seconds == pytest.approx(7200)
    assert updated.created_at.tzinfo is not None


async def test_tokens_are_found_and_deleted_by_owner_and_project(token_db):
    first = await token_db.create(_get_token("t-1"))
    await token_db.create(_get_token("t-2"))
    other_user_ids = [generate_id()]

    found = await token_db.get_many(
        {
            "user_id": _USER_ID,
            "id": {"$in": [first.id]},
            "lifespan_seconds": {"$gte": 1},
        }
    )
    deleted = await token_db.delete_many(
        {"user_id": {"$nin": other_user_ids}, "project_id": _PROJECT_ID}
    )

    assert found == [first]
    assert deleted == 2
    with pytest.raises(AppTokenNotFound):
        await token_db.delete_one({"id": first.id})


def _get_token(token: str = "t-1", lifespan_seconds: float = 3600) -> AppToken:
    # in milliseconds, which are all MongoDB keeps of a datetime
    now = datetime.now(timezone.utc)
    return AppToken(
        created_at=now.replace(microsecond=now.microsecond // 1000 * 1000),
        title="token",
        token=token,
        user_id=_USER_ID,
        project_id=_PROJECT_ID,
        lifespan_seconds=lifespan_seconds,
    )
