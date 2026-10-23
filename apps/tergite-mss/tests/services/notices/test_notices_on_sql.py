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
"""The notices service on each SQL database: dismissals, read states, expiry and emails"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from libs.storage import Database, generate_id
from services import notices
from services.notices import Notice, NoticeType
from services.notices import service as notices_service
from services.notices.dtos import ProjectRequestContext, RefType
from services.notices.emails import process_email_batch_results
from utils.config import NoticesConfig

_USER_ID = generate_id()
_OTHER_USER_ID = generate_id()
_ADMIN_ID = generate_id()
_REQUESTER = SimpleNamespace(id=_USER_ID, is_superuser=False)


@pytest.fixture
async def database(sql_database_url, monkeypatch):
    database = Database(sql_database_url, schemas=notices.SCHEMAS)
    await database.setup()
    # on_startup sets the service's module state, which the running app shares
    for name in ("_database", "_conf", "_is_email_enabled"):
        monkeypatch.setattr(notices_service, name, getattr(notices_service, name))
    await notices_service.on_startup(database, None, conf=NoticesConfig())
    yield database
    await database.close()


async def test_system_notices_are_written_per_user_from_their_template(database):
    created = await notices.create_system_notice(
        user_ids=[_USER_ID, _OTHER_USER_ID],
        notice_type=NoticeType.PROJECT_MEMBERSHIP_GRANTED.id,
        context=ProjectRequestContext(project_name="p"),
        ref_type=RefType.PROJECT,
        ref_id=generate_id(),
    )

    found = await notices.find_many(database, user_id=_USER_ID)

    assert len(created) == 2
    assert [notice.id for notice in found] == [created[0].id]
    assert "p" in found[0].title + found[0].body


async def test_direct_and_broadcast_notices_are_read_and_unread(database):
    direct = await database.insert(Notice, _get_notice(user_id=_USER_ID))
    broadcast = await database.insert(
        Notice, _get_notice(type=NoticeType.CUSTOM_BROADCAST.id)
    )

    read_direct = await notices.set_read_status(database, direct.id, _USER_ID, True)
    read_broadcast = await notices.set_read_status(
        database, broadcast.id, _USER_ID, True
    )
    unread = await notices.find_many(database, user_id=_USER_ID, is_read=False)
    still_shown = await notices.find_many(database, user_id=_OTHER_USER_ID)

    assert read_direct.read_at is not None and read_direct.dismissed_by == [_USER_ID]
    assert read_broadcast.read_at is None and read_broadcast.dismissed_by == [_USER_ID]
    assert unread == []
    assert [notice.id for notice in still_shown] == [broadcast.id]
    assert (
        await notices.count_many(
            database, _REQUESTER, is_read=True, should_include_dismissed=True
        )
        == 2
    )

    count = await notices.set_read_status_many(database, _USER_ID, False)
    assert count == 2
    assert await notices.count_many(database, _REQUESTER, is_read=False) == 2


async def test_notices_are_filtered_by_type_time_and_expiry(database):
    now = datetime.now(timezone.utc)
    current = await database.insert(
        Notice, _get_notice(user_id=_USER_ID, starts_at=now - timedelta(hours=1))
    )
    await database.insert(
        Notice, _get_notice(user_id=_USER_ID, expires_at=now - timedelta(hours=1))
    )

    by_time = await notices.find_many(
        database, user_id=_USER_ID, min_start_utc=now - timedelta(hours=2)
    )
    by_type = await notices.find_many(
        database, user_id=_USER_ID, types=[NoticeType.CUSTOM.id]
    )

    assert [notice.id for notice in by_time] == [current.id]
    assert [notice.id for notice in by_type] == [current.id]


async def test_notices_of_a_reference_are_cleared(database):
    ref_id = generate_id()
    await database.insert(
        Notice, _get_notice(user_id=_USER_ID, ref_type=RefType.PROJECT, ref_id=ref_id)
    )
    await database.insert(
        Notice,
        _get_notice(
            type=NoticeType.CUSTOM_BROADCAST.id, ref_type=RefType.PROJECT, ref_id=ref_id
        ),
    )

    count = await notices.clear_notices_by_reference({RefType.PROJECT: [ref_id]})

    assert count == 2
    assert await notices.find_many(database, user_id=_USER_ID) == []


async def test_email_preferences_and_attempts_are_kept(database):
    custom = NoticeType.CUSTOM.id
    notice = await database.insert(Notice, _get_notice(user_id=_USER_ID))

    await notices.set_email_preferences(database, _USER_ID, {custom: False})
    prefs = await notices.get_email_preferences(database, _USER_ID)
    await process_email_batch_results(
        database, [SimpleNamespace(ref_id=notice.id, is_success=True, can_retry=False)]
    )

    assert prefs[custom] is False
    assert (await notices.get_one(database, notice.id)).email_attempts == 1
    deleted = await notices.delete_notice(database, notice.id)
    assert deleted.id == notice.id


def _get_notice(**fields) -> Notice:
    """Gets a custom notice from an admin, unless fields say otherwise"""
    values = {"type": NoticeType.CUSTOM.id, "created_by": _ADMIN_ID, **fields}
    return Notice(title="t", body="b", **values)
