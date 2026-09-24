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

import pymongo.database
from beanie import PydanticObjectId
from bson import ObjectId
from starlette.testclient import TestClient

from services.notices import NoticeType
from tests._utils.auth import TEST_SUPERUSER_ID, TEST_USER_ID, TEST_OUTSIDER_ID, TEST_PROJECT_ID, TEST_OUTSIDER_EMAIL, \
    TEST_SYSTEM_USER_ID, TEST_SYSTEM_USER_EMAIL, TEST_PROJECT_EXT_ID, TEST_USER_EMAIL
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import find_in_collection
from tests._utils.records import with_offset_datetimes


_PREFS_COLLECTION = "notice_preferences"
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


def test_project_access_request_notifies_the_project_admin(client, outsider_jwt_cookie, db):
    """Filing an access request reaches the admin of the project concerned"""
    with client as client:
        _request_project_access(client, outsider_jwt_cookie)

        got = _get_user_notices(db, TEST_USER_ID)

        assert len(got) == 1
        assert got[0]["type"] == NoticeType.PROJECT_ACCESS_REQUESTED
        assert got[0]["action"]["id"] == "user-request"
        assert "test-project" in got[0]["title"]
        assert got[0]["read_at"] is None


def test_project_access_request_does_not_notify_the_requester(client, outsider_jwt_cookie, db):
    """The requester is not their own approver, so gets nothing on filing"""
    with client as client:
        _request_project_access(client, outsider_jwt_cookie)

        assert _get_user_notices(db, TEST_OUTSIDER_ID) == []


def test_approval_notifies_the_requester(
    client, outsider_jwt_cookie, user_jwt_cookie, db
):
    """The decision reaches the person who asked"""
    with client as client:
        request_id = _request_project_access(client, outsider_jwt_cookie).json()["id"]
        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        got = _get_user_notices(db, TEST_OUTSIDER_ID)

        assert [item["type"] for item in got] == [
            NoticeType.PROJECT_ACCESS_APPROVED
        ]
        assert "test-project" in got[0]["title"]


def test_rejection_notifies_the_requester_with_the_reason(
    client, outsider_jwt_cookie, user_jwt_cookie, db
):
    """A rejection carries its reason through to the notification body"""
    with client as client:
        request_id = _request_project_access(client, outsider_jwt_cookie).json()["id"]
        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "rejected", "rejection_reason": "wrong team"},
        )

        got = _get_user_notices(db, TEST_OUTSIDER_ID)

        assert got[0]["type"] == NoticeType.PROJECT_ACCESS_REJECTED
        assert "wrong team" in got[0]["body"]


def test_qpu_request_notifies_superusers(client, user_jwt_cookie, db):
    """QPU time is a system allocation, so the request reaches superusers"""
    with client as client:
        response = client.post(
            "/admin/qpu-time-requests/",
            cookies=user_jwt_cookie,
            json={
                "project_id": TEST_PROJECT_ID,
                "seconds": 120,
                "reason": "more please",
            },
        )
        assert response.status_code == 201

        got = _get_user_notices(db, TEST_SUPERUSER_ID)

        assert [item["type"] for item in got] == [
            NoticeType.QPU_SECONDS_REQUESTED
        ]
        assert "120s" in got[0]["body"]
        assert _get_user_notices(db, TEST_USER_ID) == []


def test_qpu_grant_notifies_the_requester(
    client, user_jwt_cookie, admin_jwt_cookie, db
):
    """Granting QPU time tells the requester how much they got"""
    with client as client:
        request_id = client.post(
            "/admin/qpu-time-requests/",
            cookies=user_jwt_cookie,
            json={"project_id": TEST_PROJECT_ID, "seconds": 300, "reason": "x"},
        ).json()["id"]

        client.put(
            f"/admin/user-requests/{request_id}",
            cookies=admin_jwt_cookie,
            json={"status": "approved"},
        )

        got = _get_user_notices(db, TEST_USER_ID)

        assert [item["type"] for item in got] == [NoticeType.QPU_SECONDS_GRANTED]
        assert "300s" in got[0]["title"]


def test_project_creation_notifies_the_new_members(client, admin_jwt_cookie, db):
    """Everyone put on a brand new project is told they were added"""
    with client as client:
        response = _create_project(client, admin_jwt_cookie)
        assert response.status_code == 201

        user_notice_types = _get_user_notice_types(db, TEST_OUTSIDER_ID)
        assert user_notice_types == [
            NoticeType.PROJECT_MEMBERSHIP_GRANTED
        ]


def test_project_creation_notifies_the_admin(client, admin_jwt_cookie, db):
    """The user named as admin hears about that, not only about membership"""
    with client as client:
        assert _create_project(client, admin_jwt_cookie).status_code == 201

        assert set(_get_user_notice_types(db, TEST_USER_ID)) == {
            NoticeType.PROJECT_MEMBERSHIP_GRANTED,
            NoticeType.PROJECT_ADMIN_ASSIGNED,
        }


def test_project_update_notifies_the_added_and_the_removed(
    client, admin_jwt_cookie, db
):
    """Replacing the member list is a grant for some and a revocation for others"""
    with client as client:
        response = client.put(
            f"/admin/projects/{TEST_PROJECT_ID}",
            json={"user_emails": [TEST_OUTSIDER_EMAIL]},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert NoticeType.PROJECT_MEMBERSHIP_GRANTED in _get_user_notice_types(db, TEST_OUTSIDER_ID)
        assert NoticeType.PROJECT_MEMBERSHIP_REVOKED in _get_user_notice_types(db, TEST_SYSTEM_USER_ID)


def test_project_update_notifies_the_new_admin(client, admin_jwt_cookie, db):
    """Handing a project to someone else tells them they now run it"""
    with client as client:
        response = client.put(
            f"/admin/projects/{TEST_PROJECT_ID}",
            json={"admin_email": TEST_SYSTEM_USER_EMAIL},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert NoticeType.PROJECT_ADMIN_ASSIGNED in _get_user_notice_types(db, TEST_SYSTEM_USER_ID)


def test_project_update_that_changes_no_membership_notifies_nobody(
    client, admin_jwt_cookie, db
):
    """A rename must not spam every member"""
    with client as client:
        before = db[_NOTICES_COLLECTION].count_documents({})

        response = client.put(
            f"/admin/projects/{TEST_PROJECT_ID}",
            json={"name": "a new name"},
            cookies=admin_jwt_cookie,
        )

        assert response.status_code == 200
        assert db[_NOTICES_COLLECTION].count_documents({}) == before


def test_view_my_notifications(client, outsider_jwt_cookie, user_jwt_cookie):
    """GET /me/notices/ returns only the caller's own notices"""
    with client as client:
        _request_project_access(client, outsider_jwt_cookie)

        admin_view = client.get("/me/notices/", cookies=user_jwt_cookie).json()
        requester_view = client.get("/me/notices/", cookies=outsider_jwt_cookie).json()

        assert len(admin_view["data"]) == 1
        assert requester_view["data"] == []


def test_filter_notifications_by_type(client, outsider_jwt_cookie, user_jwt_cookie):
    """The type query param narrows the list"""
    with client as client:
        _request_project_access(client, outsider_jwt_cookie)

        matching = client.get(
            "/me/notices/?type=project-access-requested", cookies=user_jwt_cookie
        ).json()
        other = client.get(
            "/me/notices/?type=qpu-seconds-granted", cookies=user_jwt_cookie
        ).json()

        assert len(matching["data"]) == 1
        assert other["data"] == []


def test_mark_notification_read(client, outsider_jwt_cookie, user_jwt_cookie):
    """PUT /me/notices/{pk} stamps read_at and the unread filter reflects it"""
    with client as client:
        _request_project_access(client, outsider_jwt_cookie)
        pk = client.get("/me/notices/", cookies=user_jwt_cookie).json()["data"][0]["id"]

        response = client.put(
            f"/me/notices/{pk}", cookies=user_jwt_cookie, json={"is_read": True}
        )

        assert response.status_code == 200
        assert response.json()["read_at"] is not None

        unread = client.get(
            "/me/notices/?is_read=false", cookies=user_jwt_cookie
        ).json()
        assert unread["data"] == []


def test_mark_notification_unread(client, outsider_jwt_cookie, user_jwt_cookie):
    """Read state is reversible"""
    with client as client:
        _request_project_access(client, outsider_jwt_cookie)
        pk = client.get("/me/notices/", cookies=user_jwt_cookie).json()["data"][0]["id"]
        client.put(f"/me/notices/{pk}", cookies=user_jwt_cookie, json={"is_read": True})

        response = client.put(
            f"/me/notices/{pk}", cookies=user_jwt_cookie, json={"is_read": False}
        )

        assert response.json()["read_at"] is None


def test_cannot_mark_another_users_notification(
    client, outsider_jwt_cookie, user_jwt_cookie
):
    """One user cannot touch another's notification, even knowing its id"""
    with client as client:
        _request_project_access(client, outsider_jwt_cookie)
        pk = client.get("/me/notices/", cookies=user_jwt_cookie).json()["data"][0]["id"]

        response = client.put(
            f"/me/notices/{pk}",
            cookies=outsider_jwt_cookie,
            json={"is_read": True},
        )

        assert response.status_code == 404


def test_mark_all_read(client, outsider_jwt_cookie, user_jwt_cookie):
    """PUT /me/notices/ marks the whole list read"""
    with client as client:
        _request_project_access(client, outsider_jwt_cookie)

        response = client.put(
            "/me/notices/", cookies=user_jwt_cookie, json={"is_read": True}
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "detail": "1 notices updated",
        }
        unread = client.get(
            "/me/notices/?is_read=false", cookies=user_jwt_cookie
        ).json()
        assert unread["data"] == []


def test_notification_count(client, outsider_jwt_cookie, user_jwt_cookie):
    """GET /counts/notices mirrors the notices count endpoint"""
    with client as client:
        _request_project_access(client, outsider_jwt_cookie)

        response = client.get("/counts/notices?is_read=false", cookies=user_jwt_cookie)

        assert response.status_code == 200
        assert response.json() == {"count": 1}


def test_unauthenticated_notifications_view(client):
    """Notifications need a signed-in user"""
    with client as client:
        assert client.get("/me/notices/").status_code == 401


def test_default_preferences(client, user_jwt_cookie):
    """Every known type has a preference, defaulted from the channel policy"""
    with client as client:
        got = client.get("/me/notification-preferences/", cookies=user_jwt_cookie)

        assert got.status_code == 200
        assert set(got.json()) == {item.value for item in CHANNEL_POLICY}
        assert all(value["in_app"] for value in got.json().values())


def test_update_preferences(client, user_jwt_cookie, db):
    """A partial update changes only the named type and persists"""
    with client as client:
        response = client.put(
            "/me/notification-preferences/",
            cookies=user_jwt_cookie,
            json={"qpu-seconds-granted": {"in_app": True, "email": False}},
        )

        got = response.json()
        assert response.status_code == 200
        assert got["qpu-seconds-granted"]["email"] is False
        assert got["project-access-approved"]["email"] is True
        assert db[_PREFS_COLLECTION].count_documents({}) == 1


def test_mandatory_in_app_cannot_be_silenced(client, user_jwt_cookie):
    """Silencing an in-app-mandatory type is ignored rather than rejected"""
    with client as client:
        response = client.put(
            "/me/notification-preferences/",
            cookies=user_jwt_cookie,
            json={"project-access-requested": {"in_app": False, "email": False}},
        )

        got = response.json()
        assert got["project-access-requested"]["in_app"] is True
        assert got["project-access-requested"]["email"] is False


def test_optional_in_app_can_be_silenced(
    client, outsider_jwt_cookie, user_jwt_cookie, db, mocker
):
    """A type the policy allows silencing is not delivered in-app once opted out"""
    mocker.patch.dict(
        CHANNEL_POLICY,
        {
            NoticeType.PROJECT_ACCESS_REQUESTED: ChannelPolicy(
                in_app_mandatory=False, email_default=True
            )
        },
    )

    with client as client:
        client.put(
            "/me/notification-preferences/",
            cookies=user_jwt_cookie,
            json={"project-access-requested": {"in_app": False, "email": False}},
        )

        _request_project_access(client, outsider_jwt_cookie)

        assert _get_user_notices(db, TEST_USER_ID) == []


def test_render_tolerates_a_missing_context_value():
    """A missing optional field renders empty rather than failing the notification"""
    got = render(NoticeType.PROJECT_ACCESS_REJECTED, {"project_name": "alpha"})

    assert "alpha" in got.title
    # no unreplaced placeholder survives into the copy the recipient sees
    assert "{" not in got.body and "}" not in got.body
    assert "approver_name" not in got.body


def test_project_without_an_admin_still_accepts_requests(
    client, outsider_jwt_cookie, db
):
    """An admin-less project has no approver to notify, and must not break filing"""
    db["auth_projects"].update_one(
        {"ext_id": TEST_PROJECT_EXT_ID}, {"$set": {"admin_id": None}}
    )

    with client as client:
        response = _request_project_access(client, outsider_jwt_cookie)

        assert response.status_code == 201
        assert db[_NOTICES_COLLECTION].count_documents({}) == 0


def test_deciding_a_request_clears_its_prompt(
    client, outsider_jwt_cookie, user_jwt_cookie, db
):
    """Approving anywhere marks the 'please decide this' notification read

    The dropdown's own buttons are not the only way to decide a request; doing it from
    the approvals page used to leave the prompt sitting there unread.
    """
    with client as client:
        request_id = _request_project_access(client, outsider_jwt_cookie).json()["id"]
        prompt = client.get("/me/notices/", cookies=user_jwt_cookie).json()["data"][0]
        assert prompt["read_at"] is None
        assert prompt["action"]["request_id"] == request_id

        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        got = db[_NOTICES_COLLECTION].find_one({"_id": PydanticObjectId(prompt["id"])})
        assert got["read_at"] is not None


def test_deciding_a_request_leaves_the_outcome_unread(
    client, outsider_jwt_cookie, user_jwt_cookie
):
    """Only the actionable prompt is cleared; the requester's outcome is still news"""
    with client as client:
        request_id = _request_project_access(client, outsider_jwt_cookie).json()["id"]
        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        outcome = client.get(
            "/me/notices/?is_read=false", cookies=outsider_jwt_cookie
        ).json()["data"]
        assert len(outcome) == 1
        assert outcome[0]["type"] == "project-access-approved"


def test_read_filter_matches_only_read_notifications(
    client, outsider_jwt_cookie, user_jwt_cookie
):
    """is_read=true returns the read ones, complementing the unread filter"""
    with client as client:
        _request_project_access(client, outsider_jwt_cookie)
        pk = client.get("/me/notices/", cookies=user_jwt_cookie).json()["data"][0]["id"]

        before = client.get("/me/notices/?is_read=true", cookies=user_jwt_cookie).json()
        client.put(f"/me/notices/{pk}", cookies=user_jwt_cookie, json={"is_read": True})
        after = client.get("/me/notices/?is_read=true", cookies=user_jwt_cookie).json()

        assert before["data"] == []
        assert len(after["data"]) == 1


def test_emission_failure_does_not_fail_the_request(
    client, outsider_jwt_cookie, db, mocker
):
    """A notification is a side effect, so its failure must not fail the operation"""
    mocker.patch(
        "services.notices.service.Notification.insert_many",
        side_effect=RuntimeError("mongo is sad"),
    )

    with client as client:
        response = _request_project_access(client, outsider_jwt_cookie)

        assert response.status_code == 201
        assert _get_user_notices(db, TEST_USER_ID) == []


def _request_project_access(client, cookie, ext_id=TEST_PROJECT_EXT_ID, reason="let me in"):
    """A helper to request for project access"""
    return client.post(
        "/me/requests/",
        cookies=cookie,
        json={"type": "project-access", "project_ext_id": ext_id, "reason": reason},
    )


def _get_user_notices(db: pymongo.database.Database, user_id: Any):
    """Gets the notices of a given user

    Args:
        db: the database where notices are stored
        user_id: the identifier of the user

    Returns:
        A list of dictionaries that represent the notices
    """
    result = db[_NOTICES_COLLECTION].find({"user_id": PydanticObjectId(user_id)}).sort("created_at")
    return list(result)


def _get_user_notice_types(db: pymongo.database.Database, user_id: Any):
    """Gets the types of notices sent to a given user

    Args:
        db: the database where notices are stored
        user_id: the identifier of the user

    Returns:
        A list of strings representing the types of the notices
    """
    return [item["type"] for item in _get_user_notices(db, user_id)]


def _create_project(client: TestClient, cookie: str, **options):
    """Creates a given project with good defaults

    Args:
        client: the http (test) client to use to create the project
        cookie: the cookie to use to create the project
        options: the args to override the default args of projects

    Returns:
        the HTTP response obtained on project creation
    """
    body = {
        "admin_email": TEST_USER_EMAIL,
        "user_emails": [TEST_OUTSIDER_EMAIL],
        "ext_id": "notified-project",
        "is_active": True,
        "name": "notified project",
        "description": "a project whose members hear about it",
        "qpu_seconds": 100,
        **options,
    }
    return client.post("/admin/projects/", json=body, cookies=cookie)


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
