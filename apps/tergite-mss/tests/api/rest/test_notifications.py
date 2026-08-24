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

"""Tests for the /me/notifications endpoints and notification emission"""
import pytest
from beanie import PydanticObjectId

from services.notifications import CHANNEL_POLICY, NotificationType
from services.notifications.templates import ChannelPolicy, render
from tests._utils.auth import (
    TEST_OUTSIDER_ID,
    TEST_PROJECT_EXT_ID,
    TEST_PROJECT_ID,
    TEST_SUPERUSER_ID,
    TEST_USER_ID,
)
from utils import rate_limit

_COLLECTION = "notifications"
_PREFS_COLLECTION = "notification_preferences"


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Rate limit counters outlive a test's database, so clear them explicitly"""
    yield
    for user_id in (TEST_OUTSIDER_ID, TEST_USER_ID, TEST_SUPERUSER_ID):
        rate_limit.reset(f"project-lookup:{user_id}")


def _request_access(client, cookie, ext_id=TEST_PROJECT_EXT_ID, reason="let me in"):
    return client.post(
        "/me/requests/",
        cookies=cookie,
        json={"type": "project-access", "project_ext_id": ext_id, "reason": reason},
    )


def _notifications_for(db, user_id):
    return list(
        db[_COLLECTION].find({"user_id": PydanticObjectId(user_id)}).sort("created_at")
    )


def test_request_notifies_the_project_admin(client, outsider_jwt_cookie, db):
    """Filing an access request reaches the admin of the project concerned"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        got = _notifications_for(db, TEST_USER_ID)

        assert len(got) == 1
        assert got[0]["type"] == NotificationType.PROJECT_ACCESS_REQUESTED
        assert got[0]["action"]["kind"] == "user-request"
        assert "test-project" in got[0]["title"]
        assert got[0]["read_at"] is None


def test_request_does_not_notify_the_requester(client, outsider_jwt_cookie, db):
    """The requester is not their own approver, so gets nothing on filing"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        assert _notifications_for(db, TEST_OUTSIDER_ID) == []


def test_approval_notifies_the_requester(
    client, outsider_jwt_cookie, user_jwt_cookie, db
):
    """The decision reaches the person who asked"""
    with client as client:
        request_id = _request_access(client, outsider_jwt_cookie).json()["id"]
        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        got = _notifications_for(db, TEST_OUTSIDER_ID)

        assert [item["type"] for item in got] == [
            NotificationType.PROJECT_ACCESS_APPROVED
        ]
        assert "test-project" in got[0]["title"]


def test_rejection_notifies_the_requester_with_the_reason(
    client, outsider_jwt_cookie, user_jwt_cookie, db
):
    """A rejection carries its reason through to the notification body"""
    with client as client:
        request_id = _request_access(client, outsider_jwt_cookie).json()["id"]
        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "rejected", "rejection_reason": "wrong team"},
        )

        got = _notifications_for(db, TEST_OUTSIDER_ID)

        assert got[0]["type"] == NotificationType.PROJECT_ACCESS_REJECTED
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

        got = _notifications_for(db, TEST_SUPERUSER_ID)

        assert [item["type"] for item in got] == [
            NotificationType.QPU_SECONDS_REQUESTED
        ]
        assert "120s" in got[0]["body"]
        assert _notifications_for(db, TEST_USER_ID) == []


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

        got = _notifications_for(db, TEST_USER_ID)

        assert [item["type"] for item in got] == [NotificationType.QPU_SECONDS_GRANTED]
        assert "300s" in got[0]["title"]


def test_view_my_notifications(client, outsider_jwt_cookie, user_jwt_cookie):
    """GET /me/notifications/ returns only the caller's own notifications"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        admin_view = client.get("/me/notifications/", cookies=user_jwt_cookie).json()
        requester_view = client.get(
            "/me/notifications/", cookies=outsider_jwt_cookie
        ).json()

        assert len(admin_view["data"]) == 1
        assert requester_view["data"] == []


def test_filter_notifications_by_type(client, outsider_jwt_cookie, user_jwt_cookie):
    """The type query param narrows the list"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        matching = client.get(
            "/me/notifications/?type=project-access-requested", cookies=user_jwt_cookie
        ).json()
        other = client.get(
            "/me/notifications/?type=qpu-seconds-granted", cookies=user_jwt_cookie
        ).json()

        assert len(matching["data"]) == 1
        assert other["data"] == []


def test_mark_notification_read(client, outsider_jwt_cookie, user_jwt_cookie):
    """PUT /me/notifications/{pk} stamps read_at and the unread filter reflects it"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)
        pk = client.get("/me/notifications/", cookies=user_jwt_cookie).json()["data"][
            0
        ]["id"]

        response = client.put(
            f"/me/notifications/{pk}", cookies=user_jwt_cookie, json={"is_read": True}
        )

        assert response.status_code == 200
        assert response.json()["read_at"] is not None

        unread = client.get(
            "/me/notifications/?is_read=false", cookies=user_jwt_cookie
        ).json()
        assert unread["data"] == []


def test_mark_notification_unread(client, outsider_jwt_cookie, user_jwt_cookie):
    """Read state is reversible"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)
        pk = client.get("/me/notifications/", cookies=user_jwt_cookie).json()["data"][
            0
        ]["id"]
        client.put(
            f"/me/notifications/{pk}", cookies=user_jwt_cookie, json={"is_read": True}
        )

        response = client.put(
            f"/me/notifications/{pk}", cookies=user_jwt_cookie, json={"is_read": False}
        )

        assert response.json()["read_at"] is None


def test_cannot_mark_another_users_notification(
    client, outsider_jwt_cookie, user_jwt_cookie
):
    """One user cannot touch another's notification, even knowing its id"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)
        pk = client.get("/me/notifications/", cookies=user_jwt_cookie).json()["data"][
            0
        ]["id"]

        response = client.put(
            f"/me/notifications/{pk}",
            cookies=outsider_jwt_cookie,
            json={"is_read": True},
        )

        assert response.status_code == 404


def test_mark_all_read(client, outsider_jwt_cookie, user_jwt_cookie):
    """PUT /me/notifications/ marks the whole list read"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        response = client.put(
            "/me/notifications/", cookies=user_jwt_cookie, json={"is_read": True}
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "detail": "1 notifications updated",
        }
        unread = client.get(
            "/me/notifications/?is_read=false", cookies=user_jwt_cookie
        ).json()
        assert unread["data"] == []


def test_notification_count(client, outsider_jwt_cookie, user_jwt_cookie):
    """GET /counts/notifications mirrors the notices count endpoint"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)

        response = client.get(
            "/counts/notifications?is_read=false", cookies=user_jwt_cookie
        )

        assert response.status_code == 200
        assert response.json() == {"count": 1}


def test_unauthenticated_notifications_view(client):
    """Notifications need a signed-in user"""
    with client as client:
        assert client.get("/me/notifications/").status_code == 401


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
            NotificationType.PROJECT_ACCESS_REQUESTED: ChannelPolicy(
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

        _request_access(client, outsider_jwt_cookie)

        assert _notifications_for(db, TEST_USER_ID) == []


def test_render_tolerates_a_missing_context_value():
    """A missing optional field renders empty rather than failing the notification"""
    got = render(NotificationType.PROJECT_ACCESS_REJECTED, {"project_name": "alpha"})

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
        response = _request_access(client, outsider_jwt_cookie)

        assert response.status_code == 201
        assert db[_COLLECTION].count_documents({}) == 0


def test_deciding_a_request_clears_its_prompt(
    client, outsider_jwt_cookie, user_jwt_cookie, db
):
    """Approving anywhere marks the 'please decide this' notification read

    The dropdown's own buttons are not the only way to decide a request; doing it from
    the approvals page used to leave the prompt sitting there unread.
    """
    with client as client:
        request_id = _request_access(client, outsider_jwt_cookie).json()["id"]
        prompt = client.get("/me/notifications/", cookies=user_jwt_cookie).json()[
            "data"
        ][0]
        assert prompt["read_at"] is None
        assert prompt["action"]["request_id"] == request_id

        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        got = db[_COLLECTION].find_one({"_id": PydanticObjectId(prompt["id"])})
        assert got["read_at"] is not None


def test_deciding_a_request_leaves_the_outcome_unread(
    client, outsider_jwt_cookie, user_jwt_cookie
):
    """Only the actionable prompt is cleared; the requester's outcome is still news"""
    with client as client:
        request_id = _request_access(client, outsider_jwt_cookie).json()["id"]
        client.put(
            f"/me/requests/{request_id}",
            cookies=user_jwt_cookie,
            json={"status": "approved"},
        )

        outcome = client.get(
            "/me/notifications/?is_read=false", cookies=outsider_jwt_cookie
        ).json()["data"]
        assert len(outcome) == 1
        assert outcome[0]["type"] == "project-access-approved"


def test_read_filter_matches_only_read_notifications(
    client, outsider_jwt_cookie, user_jwt_cookie
):
    """is_read=true returns the read ones, complementing the unread filter"""
    with client as client:
        _request_access(client, outsider_jwt_cookie)
        pk = client.get("/me/notifications/", cookies=user_jwt_cookie).json()["data"][
            0
        ]["id"]

        before = client.get(
            "/me/notifications/?is_read=true", cookies=user_jwt_cookie
        ).json()
        client.put(
            f"/me/notifications/{pk}", cookies=user_jwt_cookie, json={"is_read": True}
        )
        after = client.get(
            "/me/notifications/?is_read=true", cookies=user_jwt_cookie
        ).json()

        assert before["data"] == []
        assert len(after["data"]) == 1


def test_emission_failure_does_not_fail_the_request(
    client, outsider_jwt_cookie, db, mocker
):
    """A notification is a side effect, so its failure must not fail the operation"""
    mocker.patch(
        "services.notifications.service.Notification.insert_many",
        side_effect=RuntimeError("mongo is sad"),
    )

    with client as client:
        response = _request_access(client, outsider_jwt_cookie)

        assert response.status_code == 201
        assert _notifications_for(db, TEST_USER_ID) == []
