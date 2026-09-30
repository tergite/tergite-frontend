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

from datetime import datetime, timezone
from typing import Any, Dict, List

from bson import ObjectId

from tests._utils.auth import (
    TEST_SUPERUSER_EMAIL,
    TEST_SUPERUSER_ID,
    TEST_USER_EMAIL,
    TEST_USER_ID,
)
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import find_in_collection
from tests._utils.records import with_offset_datetimes

_NOTICES_COLLECTION = "notices"
_NOTICES_IN_DB_RAW = load_json_fixture("notices.json")

# IDs of the notices in the fixture (mirrors the _id fields in notices.json)
_NOTICE_TARGETING_ADMIN_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"

# Individual raw fixture dicts for tests that need to insert a single notice
_NOTICE_TARGETING_ADMIN_RAW = next(
    n for n in _NOTICES_IN_DB_RAW if n["_id"] == _NOTICE_TARGETING_ADMIN_ID
)


def test_admin_publish_notice(admin_jwt_cookie, client, db):
    """Admin can publish a notice via POST /admin/notices/"""
    payload = {
        "message": "Important maintenance window",
        "severity": "warning",
        "starts_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
    }
    with client as client:
        response = client.post(
            "/admin/notices/", cookies=admin_jwt_cookie, json=payload
        )
        got = response.json()

        assert response.status_code == 200
        assert isinstance(got["id"], str)
        assert got["message"] == payload["message"]
        assert got["severity"] == payload["severity"]
        assert got["created_by"] == TEST_SUPERUSER_ID
        assert got["target_user_ids"] is None
        assert got["dismissed_by"] == []

        # verify notice was persisted to db
        notices = find_in_collection(db, _NOTICES_COLLECTION)
        assert len(notices) == 1
        assert str(notices[0]["_id"]) == got["id"]


def test_admin_publish_notice_with_target_emails(admin_jwt_cookie, client, db):
    """Admin can publish a targeted notice via POST /admin/notices/ with target_user_emails"""
    payload = {
        "message": "Notice for specific users",
        "severity": "info",
        "starts_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
        "target_user_emails": [TEST_USER_EMAIL, TEST_SUPERUSER_EMAIL],
    }
    with client as client:
        response = client.post(
            "/admin/notices/", cookies=admin_jwt_cookie, json=payload
        )
        got = response.json()

        assert response.status_code == 200
        assert isinstance(got["id"], str)
        assert got["target_user_ids"] is not None
        assert len(got["target_user_ids"]) == 2
        assert TEST_USER_ID in got["target_user_ids"]
        assert TEST_SUPERUSER_ID in got["target_user_ids"]


def test_non_admin_publish_notice(user_jwt_cookie, client, db):
    """Non-admin cannot publish a notice via POST /admin/notices/"""
    payload = {
        "message": "Should not be created",
        "severity": "info",
        "starts_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
    }
    with client as client:
        response = client.post("/admin/notices/", cookies=user_jwt_cookie, json=payload)
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}
        assert find_in_collection(db, _NOTICES_COLLECTION) == []


def test_unauthenticated_publish_notice(client, db):
    """Unauthenticated users cannot publish a notice via POST /admin/notices/"""
    payload = {
        "message": "Should not be created",
        "severity": "info",
        "starts_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
    }
    with client as client:
        response = client.post("/admin/notices/", json=payload)
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
        assert find_in_collection(db, _NOTICES_COLLECTION) == []


def test_admin_delete_notice(admin_jwt_cookie, client, db):
    """Admin can delete a notice via DELETE /admin/notices/{notice_id}"""
    _insert_notices(db, [_NOTICE_TARGETING_ADMIN_RAW])

    with client as client:
        assert len(find_in_collection(db, _NOTICES_COLLECTION)) == 1

        response = client.delete(
            f"/admin/notices/{_NOTICE_TARGETING_ADMIN_ID}", cookies=admin_jwt_cookie
        )
        got = response.json()

        assert response.status_code == 200
        assert got["id"] == _NOTICE_TARGETING_ADMIN_ID
        assert got["message"] == _NOTICE_TARGETING_ADMIN_RAW["message"]
        assert find_in_collection(db, _NOTICES_COLLECTION) == []


def test_non_admin_delete_notice(user_jwt_cookie, client, db):
    """Non-admin cannot delete a notice via DELETE /admin/notices/{notice_id}"""
    _insert_notices(db, [_NOTICE_TARGETING_ADMIN_RAW])

    with client as client:
        response = client.delete(
            f"/admin/notices/{_NOTICE_TARGETING_ADMIN_ID}", cookies=user_jwt_cookie
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}
        assert len(find_in_collection(db, _NOTICES_COLLECTION)) == 1


def test_delete_non_existent_notice(admin_jwt_cookie, client, db):
    """DELETE /admin/notices/{notice_id} returns 404 when the notice does not exist"""
    with client as client:
        response = client.delete(
            f"/admin/notices/{_NOTICE_TARGETING_ADMIN_ID}", cookies=admin_jwt_cookie
        )
        assert response.status_code == 404


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
