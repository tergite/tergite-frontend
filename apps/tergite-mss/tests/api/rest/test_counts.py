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
"""Integration tests for the /counts routes"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from urllib import parse as urlparse

import pymongo.database
from bson import ObjectId

from ..._utils.auth import TEST_USER_ID
from ..._utils.fixtures import load_json_fixture
from ..._utils.records import with_offset_datetimes

_NOTICES_COLLECTION = "notices"
_NOTICES_IN_DB_RAW = load_json_fixture("notices.json")

# IDs mirroring notices.json
_NOTICE_TARGETING_ADMIN_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"
_NOTICE_TARGETING_USER_ID = "bbbbbbbbbbbbbbbbbbbbbbbb"
_NOTICE_BROADCAST_ID = "cccccccccccccccccccccccc"
_NOTICE_DISMISSED_BY_USER_ID = "dddddddddddddddddddddddd"
_NOTICE_FUTURE_ID = "eeeeeeeeeeeeeeeeeeeeeeee"


def test_admin_count_all_notices(admin_jwt_cookie, client, db):
    """Admin can count all notices without a user_id filter via GET /counts/notices"""
    _insert_notices(db, _NOTICES_IN_DB_RAW)

    with client as client:
        response = client.get("/counts/notices", cookies=admin_jwt_cookie)

        assert response.status_code == 200
        assert response.json() == {"count": len(_NOTICES_IN_DB_RAW)}


def test_admin_count_empty_notices(admin_jwt_cookie, client, db):
    """GET /counts/notices returns count of 0 when no notices exist"""
    with client as client:
        response = client.get("/counts/notices", cookies=admin_jwt_cookie)

        assert response.status_code == 200
        assert response.json() == {"count": 0}


def test_admin_count_notices_filtered_by_user_id(admin_jwt_cookie, client, db):
    """Admin can filter the notice count by user_id via GET /counts/notices?user_id=...&include_dismissed=true

    Only notices with target_user_ids containing the user_id plus broadcast ones are counted.
    """
    _insert_notices(db, _NOTICES_IN_DB_RAW)
    # With include_dismissed=True: all notices targeting TEST_USER_ID
    expected_count = sum(
        1
        for n in _NOTICES_IN_DB_RAW
        if n["target_user_ids"]
        and TEST_USER_ID in n["target_user_ids"]
        or n["target_user_ids"] is None
    )

    with client as client:
        response = client.get(
            f"/counts/notices?user_id={TEST_USER_ID}&include_dismissed=true",
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert response.json() == {"count": expected_count}


def test_admin_count_notices_excludes_dismissed_by_default(
    admin_jwt_cookie, client, db
):
    """GET /counts/notices?user_id=... excludes dismissed notices by default"""
    _insert_notices(db, _NOTICES_IN_DB_RAW)
    expected_count = sum(
        1
        for n in _NOTICES_IN_DB_RAW
        if (n["target_user_ids"] is None and TEST_USER_ID not in n["dismissed_by"])
        or (
            n["target_user_ids"]
            and TEST_USER_ID in n["target_user_ids"]
            and TEST_USER_ID not in n["dismissed_by"]
        )
    )

    with client as client:
        response = client.get(
            f"/counts/notices?user_id={TEST_USER_ID}",
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert response.json() == {"count": expected_count}


def test_admin_count_notices_filtered_by_min_start_utc(admin_jwt_cookie, client, db):
    """GET /counts/notices?min_start_utc=... only counts notices starting on or after the given time

    The future notice (starts_at_offset_hours=+720) should be the only one returned when
    min_start_utc is set to now + 360 hours (halfway between now and the future notice start).
    """
    now = datetime.now(timezone.utc)
    _insert_notices(db, _NOTICES_IN_DB_RAW, now=now)
    # Midpoint between now and the future notice start (+720h); only the future notice qualifies
    min_start_utc = (now + timedelta(hours=360)).isoformat()
    expected_count = sum(
        1 for n in _NOTICES_IN_DB_RAW if n["starts_at_offset_hours"] >= 360
    )

    with client as client:
        response = client.get(
            f"/counts/notices?min_start_utc={urlparse.quote(min_start_utc)}",
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert response.json() == {"count": expected_count}


def test_admin_count_notices_filtered_by_max_expires_utc(admin_jwt_cookie, client, db):
    """GET /counts/notices?max_expires_utc=... only counts notices expiring on or before the given time

    Four notices expire at +8760h; the future notice expires at +9480h.
    Setting max_expires_utc to now + 9000h should exclude the future notice.
    """
    now = datetime.now(timezone.utc)
    _insert_notices(db, _NOTICES_IN_DB_RAW, now=now)
    # Midpoint between +8760h and +9480h; the future notice (+9480h) should be excluded
    max_expires_utc = (now + timedelta(hours=9000)).isoformat()
    expected_count = sum(
        1 for n in _NOTICES_IN_DB_RAW if n["expires_at_offset_hours"] <= 9000
    )

    with client as client:
        response = client.get(
            f"/counts/notices?max_expires_utc={urlparse.quote(max_expires_utc)}",
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert response.json() == {"count": expected_count}


def test_non_admin_can_count_notices(user_jwt_cookie, client, db):
    """Non-admin can access GET /counts/notices"""
    _insert_notices(db, _NOTICES_IN_DB_RAW)
    expected_count = sum(
        1
        for n in _NOTICES_IN_DB_RAW
        if (n["target_user_ids"] is None and TEST_USER_ID not in n["dismissed_by"])
        or (
            n["target_user_ids"]
            and TEST_USER_ID in n["target_user_ids"]
            and TEST_USER_ID not in n["dismissed_by"]
        )
    )

    with client as client:
        response = client.get("/counts/notices", cookies=user_jwt_cookie)

        assert response.status_code == 200
        assert response.json() == {"count": expected_count}


def test_unauthenticated_cannot_count_notices(client, db):
    """Unauthenticated users cannot access GET /counts/notices"""
    _insert_notices(db, _NOTICES_IN_DB_RAW)

    with client as client:
        response = client.get("/counts/notices")

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


def _insert_notices(
    db: pymongo.database.Database,
    notices_raw: List[Dict[str, Any]],
    now: datetime = None,
) -> None:
    """Inserts notices into the database, converting offset hours to datetimes and IDs to ObjectId

    Args:
        db: the mongodb database
        notices_raw: list of raw notice dicts from the fixture (with offset_hours fields)
        now: reference datetime for offset conversion; defaults to UTC now
    """
    if now is None:
        now = datetime.now(timezone.utc)

    records = with_offset_datetimes(
        notices_raw,
        {
            "starts_at": "starts_at_offset_hours",
            "expires_at": "expires_at_offset_hours",
        },
        now=now,
    )

    def _convert(k: str, v: Any) -> Any:
        if v is None:
            return None
        if k in ("_id", "created_by"):
            return ObjectId(v)
        if k in ("target_user_ids", "dismissed_by") and isinstance(v, list):
            return [ObjectId(i) for i in v]
        return v

    db[_NOTICES_COLLECTION].insert_many(
        [{k: _convert(k, v) for k, v in record.items()} for record in records]
    )
