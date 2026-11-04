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
"""The app tokens service on each database: making, finding, extending and expiry"""

from datetime import datetime, timedelta, timezone

import pytest

from libs.storage import Database, DuplicateKeyError, generate_id
from services import auth
from services.auth import AppToken, AppTokenCreate, AppTokenQuery, Project
from services.auth.app_tokens.service import delete_non_member_tokens
from utils.exc import ForbiddenError

_USER_ID = generate_id()
_PROJECT_ID = generate_id()


@pytest.fixture
async def database(database_url):
    database = Database(database_url, schemas=auth.SCHEMAS)
    await database.setup()
    yield database
    await database.close()


async def test_a_token_is_made_only_for_an_active_project_of_its_member(database):
    await database.insert(
        Project,
        Project(id=_PROJECT_ID, name="p", admin_id=_USER_ID, user_ids=[_USER_ID]),
    )
    inactive = await database.insert(
        Project,
        Project(name="q", admin_id=_USER_ID, user_ids=[_USER_ID], is_active=False),
    )
    payload = AppTokenCreate(title="t", project_id=_PROJECT_ID, lifespan_seconds=60)
    inactive_payload = AppTokenCreate(
        title="t", project_id=inactive.id, lifespan_seconds=60
    )

    token = await auth.create_app_token(database, payload, user_id=_USER_ID)

    found = await auth.find_app_tokens(database, _USER_ID, AppTokenQuery())
    assert [found_token.id for found_token in found] == [token.id]
    with pytest.raises(ForbiddenError):
        await auth.create_app_token(database, payload, user_id=generate_id())
    with pytest.raises(ForbiddenError):
        await auth.create_app_token(database, inactive_payload, user_id=_USER_ID)


async def test_a_token_is_kept_unique(database):
    await database.insert(AppToken, _get_token())

    with pytest.raises(DuplicateKeyError):
        await database.insert(AppToken, _get_token())


async def test_an_expired_token_is_deleted_when_read(database):
    token = await database.insert(AppToken, _get_token(lifespan_seconds=0))
    expires_at = token.created_at + timedelta(hours=2)

    assert (
        await auth.update_app_token_expiry(database, token.id, _USER_ID, expires_at)
        is None
    )
    assert await auth.find_app_tokens(database, _USER_ID, AppTokenQuery()) == []


async def test_a_token_lifespan_is_extended(database):
    token = await database.insert(AppToken, _get_token())
    expires_at = token.created_at + timedelta(hours=2)

    updated = await auth.update_app_token_expiry(
        database, token.id, _USER_ID, expires_at
    )

    assert updated.lifespan_seconds == pytest.approx(7200)
    assert updated.created_at.tzinfo is not None


async def test_tokens_are_found_and_deleted_by_owner_and_project(database):
    first = await database.insert(AppToken, _get_token("t-1"))
    await database.insert(AppToken, _get_token("t-2"))

    found = await auth.find_app_tokens(
        database, _USER_ID, AppTokenQuery(ids=[first.id], min_lifespan_seconds=1)
    )
    deleted = await delete_non_member_tokens(
        database, _PROJECT_ID, member_ids=[generate_id()]
    )

    assert found == [first]
    assert deleted == 2
    with pytest.raises(auth.AppTokenNotFound):
        await auth.delete_app_token(database, first.id, _USER_ID)


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
