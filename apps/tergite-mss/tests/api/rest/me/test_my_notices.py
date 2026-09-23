# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2024, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List

from bson import ObjectId

from tests._utils.auth import TEST_SUPERUSER_ID, TEST_USER_ID
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import find_in_collection
from tests._utils.records import with_offset_datetimes

_NOTICES_COLLECTION = "notices"
_NOTICES_IN_DB_RAW = load_json_fixture("notices.json")

# IDs of the notices in the fixture (mirrors the _id fields in notices.json)
_NOTICE_TARGETING_ADMIN_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"
_NOTICE_TARGETING_USER_ID = "bbbbbbbbbbbbbbbbbbbbbbbb"
_NOTICE_BROADCAST_ID = "cccccccccccccccccccccccc"
_NOTICE_DISMISSED_BY_USER_ID = "dddddddddddddddddddddddd"
_NOTICE_FUTURE_ID = "eeeeeeeeeeeeeeeeeeeeeeee"

# Individual raw fixture dicts for tests that need to insert a single notice
_NOTICE_TARGETING_ADMIN_RAW = next(
    n for n in _NOTICES_IN_DB_RAW if n["_id"] == _NOTICE_TARGETING_ADMIN_ID
)
_NOTICE_TARGETING_USER_RAW = next(
    n for n in _NOTICES_IN_DB_RAW if n["_id"] == _NOTICE_TARGETING_USER_ID
)


def test_any_user_can_dismiss_notice(user_jwt_cookie, client, db):
    """Any authenticated user can dismiss a notice via POST /admin/notices/{notice_id}/dismiss"""
    _insert_notices(db, [_NOTICE_TARGETING_USER_RAW])

    with client as client:
        response = client.post(
            f"/admin/notices/{_NOTICE_TARGETING_USER_ID}/dismiss",
            cookies=user_jwt_cookie,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        # TEST_USER_ID should now be in the dismissed_by list
        notices = find_in_collection(db, _NOTICES_COLLECTION)
        assert len(notices) == 1
        dismissed_by_strs = [str(oid) for oid in notices[0]["dismissed_by"]]
        assert TEST_USER_ID in dismissed_by_strs


def test_admin_can_dismiss_notice(admin_jwt_cookie, client, db):
    """Admin can also dismiss a notice via POST /admin/notices/{notice_id}/dismiss"""
    _insert_notices(db, [_NOTICE_TARGETING_ADMIN_RAW])

    with client as client:
        response = client.post(
            f"/admin/notices/{_NOTICE_TARGETING_ADMIN_ID}/dismiss",
            cookies=admin_jwt_cookie,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        notices = find_in_collection(db, _NOTICES_COLLECTION)
        dismissed_by_strs = [str(oid) for oid in notices[0]["dismissed_by"]]
        assert TEST_SUPERUSER_ID in dismissed_by_strs


def test_unauthenticated_dismiss_notice(client, db):
    """Unauthenticated users cannot dismiss a notice"""
    _insert_notices(db, [_NOTICE_TARGETING_USER_RAW])

    with client as client:
        response = client.post(f"/admin/notices/{_NOTICE_TARGETING_USER_ID}/dismiss")
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

        # notice should remain unchanged
        notices = find_in_collection(db, _NOTICES_COLLECTION)
        assert notices[0]["dismissed_by"] == []


def test_dismiss_non_existent_notice(user_jwt_cookie, client, db):
    """POST /admin/notices/{notice_id}/dismiss returns 404 when notice does not exist"""
    with client as client:
        response = client.post(
            f"/admin/notices/{_NOTICE_TARGETING_USER_ID}/dismiss",
            cookies=user_jwt_cookie,
        )
        assert response.status_code == 404


def test_admin_get_all_notices(admin_jwt_cookie, client, db):
    """Admin with no user_id filter retrieves all notices via GET /admin/notices"""
    _insert_notices(db, _NOTICES_IN_DB_RAW)

    with client as client:
        response = client.get("/admin/notices", cookies=admin_jwt_cookie)
        got = response.json()

        assert response.status_code == 200
        assert got["skip"] == 0
        assert got["limit"] is None
        assert len(got["data"]) == len(_NOTICES_IN_DB_RAW)


def test_admin_get_notices_filtered_by_user_id(admin_jwt_cookie, client, db):
    """Admin can filter notices by user_id via GET /admin/notices?user_id=...

    When include_dismissed=true, both active and dismissed notices for the user are returned.
    Only notices with target_user_ids containing the user_id or those with no target_user_ids are matched.
    """
    _insert_notices(db, _NOTICES_IN_DB_RAW)
    expected_ids = {
        n["_id"]
        for n in _NOTICES_IN_DB_RAW
        if (n["target_user_ids"] and TEST_USER_ID in n["target_user_ids"])
        or (n["target_user_ids"] is None)
    }

    with client as client:
        response = client.get(
            f"/admin/notices?user_id={TEST_USER_ID}&include_dismissed=true",
            cookies=admin_jwt_cookie,
        )
        got = response.json()

        assert response.status_code == 200
        returned_ids = {n["id"] for n in got["data"]}
        assert returned_ids == expected_ids


def test_admin_get_notices_excludes_dismissed_by_default(admin_jwt_cookie, client, db):
    """GET /admin/notices?user_id=... excludes dismissed notices unless include_dismissed=true"""
    _insert_notices(db, _NOTICES_IN_DB_RAW)

    with client as client:
        response = client.get(
            f"/admin/notices?user_id={TEST_USER_ID}",
            cookies=admin_jwt_cookie,
        )
        got = response.json()

        assert response.status_code == 200
        returned_ids = {n["id"] for n in got["data"]}
        assert _NOTICE_TARGETING_USER_ID in returned_ids
        assert _NOTICE_DISMISSED_BY_USER_ID not in returned_ids


def test_non_admin_get_notices_forced_to_own_user_id(user_jwt_cookie, client, db):
    """Non-admin is forced to use their own user_id when calling GET /admin/notices

    Even if a different user_id is provided in the query, the non-admin only sees
    notices that target themselves (not dismissed) and broadcast notices
    (i.e. no target_user_ids).
    """
    _insert_notices(db, _NOTICES_IN_DB_RAW)

    with client as client:
        # Non-admin tries to request admin's notices — should be ignored
        response = client.get(
            f"/admin/notices?user_id={TEST_SUPERUSER_ID}",
            cookies=user_jwt_cookie,
        )
        got = response.json()

        assert response.status_code == 200
        returned_ids = {n["id"] for n in got["data"]}
        # Should see own non-dismissed targeted notices
        assert _NOTICE_TARGETING_USER_ID in returned_ids
        # Should not see admin's notices, dismissed notices, or broadcast
        assert _NOTICE_TARGETING_ADMIN_ID not in returned_ids
        assert _NOTICE_DISMISSED_BY_USER_ID not in returned_ids
        # Broadcast (target_user_ids=None) are returned when user_id filter applies
        assert _NOTICE_BROADCAST_ID in returned_ids


def test_unauthenticated_get_notices(client, db):
    """Unauthenticated users cannot access GET /admin/notices"""
    _insert_notices(db, _NOTICES_IN_DB_RAW)

    with client as client:
        response = client.get("/admin/notices")
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


def _db_to_http_item(db_item: Dict[str, Any]) -> Dict[str, Any]:
    """Converts a database item into an item that can be expected to be returned by HTTP server

    Args:
        db_item: the item in the database

    Returns:
        the item as would be seen from an HTTP response
    """
    item = copy.deepcopy(db_item)
    item["id"] = str(item.pop("_id"))
    # fields the server fills in from model defaults
    item.setdefault("approver_scope", "system-admin")
    item.setdefault("project_id", None)
    return item


def _insert_notices(
    db, notices_raw: List[Dict[str, Any]], now: datetime = None
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
