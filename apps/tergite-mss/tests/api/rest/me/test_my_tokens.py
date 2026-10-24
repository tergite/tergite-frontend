# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Integration tests for the 'me' router"""

from datetime import datetime, timedelta, timezone
from random import randint

import pytest
from bson import ObjectId
from pytest_lazyfixture import lazy_fixture

from services.auth import AppToken
from tests._utils.auth import (
    TEST_APP_TOKEN_DICT,
    TEST_NO_QPU_APP_TOKEN_DICT,
    TEST_SUPERUSER_ID,
    TEST_USER_ID,
    get_auth_cookie,
    get_jwt_token,
)
from tests._utils.date_time import get_current_timestamp_str, get_timestamp_str
from tests._utils.mongodb import (
    get_db_record,
    update_db_record,
)
from tests.conftest import APP_TOKEN_LIST, PROJECT_LIST

# one token of each user; the rest of the fixture's tokens behave the same
_TOKENS = [APP_TOKEN_LIST[0], APP_TOKEN_LIST[2]]
_USER_ID_COOKIES_FIXTURE = [
    (TEST_USER_ID, lazy_fixture("user_jwt_cookie")),
    (TEST_SUPERUSER_ID, lazy_fixture("admin_jwt_cookie")),
]

_MY_TOKENS_REQUESTS = [
    (token["user_id"], get_auth_cookie(token["user_id"]), token) for token in _TOKENS
]
_OTHERS_TOKENS_REQUESTS = [
    (user_id, get_auth_cookie(user_id), token)
    for token in _TOKENS
    for user_id in [TEST_USER_ID, TEST_SUPERUSER_ID]
    if user_id != token["user_id"]
]
_PROJECT_USER_IDS_MAP = {
    project["_id"]: project["user_ids"] for project in PROJECT_LIST
}
_UNAUTHORIZED_TOKEN_REQUESTS = [
    (token, get_auth_cookie(user_id))
    for token in APP_TOKEN_LIST
    for user_id in [TEST_USER_ID, TEST_SUPERUSER_ID]
    if user_id not in _PROJECT_USER_IDS_MAP[token["project_id"]]
][:1]


@pytest.mark.parametrize("payload", _TOKENS)
def test_generate_app_token(payload, inserted_projects, client):
    """At /me/tokens/, user can generate app token for project they are attached to"""
    cookies = get_auth_cookie(payload["user_id"])

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post("/me/tokens/", cookies=cookies, json=payload)

        got = response.json()

        assert response.status_code == 200
        assert isinstance(got["access_token"], str)
        assert len(got["access_token"]) > 12


@pytest.mark.parametrize("payload", _TOKENS)
def test_unauthenticated_app_token_generation(payload, inserted_projects, client):
    """401 error raised at /me/tokens/ when no user jwt is sent"""

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post("/me/tokens/", json=payload)

        got = response.json()
        expected = {"detail": "Unauthorized"}
        assert response.status_code == 401
        assert got == expected


@pytest.mark.parametrize("body, cookies", _UNAUTHORIZED_TOKEN_REQUESTS)
def test_unauthorized_app_token_generation(body, cookies, inserted_projects, client):
    """403 error raised at /me/tokens/, for a project to which a user is not attached"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post("/me/tokens/", cookies=cookies, json=body)

        got = response.json()
        expected = {"detail": "Forbidden"}
        assert response.status_code == 403
        assert got == expected


@pytest.mark.parametrize("payload", _TOKENS)
def test_destroy_app_token(payload, db, client, inserted_projects, inserted_app_tokens):
    """At /me/tokens/{token}, user can destroy their own app token"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = payload["_id"]
        user_id = payload["user_id"]
        assert get_db_record(db, AppToken, _id) is not None

        url = f"/me/tokens/{_id}"
        cookies = get_auth_cookie(user_id)
        response = client.delete(url, cookies=cookies)

        assert response.status_code == 204
        assert get_db_record(db, AppToken, _id) is None


@pytest.mark.parametrize("payload", _TOKENS)
def test_destroy_expired_app_token(
    payload, db, client, inserted_projects, inserted_app_tokens
):
    """At /me/tokens/{token}, user can destroy their own expired app token"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = payload["_id"]
        user_id = payload["user_id"]
        token = get_db_record(db, AppToken, _id)
        assert token is not None

        # shift back the created_at date to a time that would make this token expired
        new_created_at = datetime.now(timezone.utc) - timedelta(
            seconds=token["lifespan_seconds"] + 1
        )
        update_obj = {"$set": {"created_at": new_created_at}}
        update_db_record(db, AppToken, _id, update=update_obj)

        url = f"/me/tokens/{_id}"
        cookies = get_auth_cookie(user_id)
        response = client.delete(url, cookies=cookies)

        assert response.status_code == 204
        assert get_db_record(db, AppToken, _id) is None


@pytest.mark.parametrize("payload", _TOKENS)
def test_unauthenticated_app_token_deletion(
    payload, db, client, inserted_projects, inserted_app_tokens
):
    """401 error raised at /me/tokens/{token} if no JWT token is passed"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = payload["_id"]
        assert get_db_record(db, AppToken, _id) is not None

        url = f"/me/tokens/{_id}"
        response = client.delete(url)
        got = response.json()
        expected = {"detail": "Unauthorized"}

        assert response.status_code == 401
        assert got == expected
        assert get_db_record(db, AppToken, _id) is not None


@pytest.mark.parametrize("payload, cookies", _UNAUTHORIZED_TOKEN_REQUESTS)
def test_unauthorized_app_token_deletion(
    payload, cookies, db, client, inserted_projects, inserted_app_tokens
):
    """403 error raised at /me/tokens/{_id}, for a project to which a user is not attached"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = payload["_id"]
        url = f"/me/tokens/{_id}"
        response = client.delete(url, cookies=cookies)

        got = response.json()
        expected = {"detail": "app token does not exist."}
        assert response.status_code == 403
        assert got == expected


@pytest.mark.parametrize("user_id, cookies", _USER_ID_COOKIES_FIXTURE)
def test_view_own_app_tokens_in_less_detail(
    user_id, cookies, client, inserted_projects, inserted_app_tokens, freezer
):
    """At /me/tokens/, user can view their own app tokens
    without the token itself displayed"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/me/tokens/", cookies=cookies)

        got = response.json()
        expected_data = [
            {
                "id": str(v["_id"]),
                "lifespan_seconds": v["lifespan_seconds"],
                "project_id": str(v["project_id"]),
                "title": v["title"],
                "created_at": get_current_timestamp_str(),
            }
            for v in [TEST_APP_TOKEN_DICT, TEST_NO_QPU_APP_TOKEN_DICT]
            + inserted_app_tokens
            if str(v["user_id"]) == user_id
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": expected_data}


@pytest.mark.parametrize("user_id, cookies, token", _MY_TOKENS_REQUESTS)
def test_view_my_app_token_in_less_detail(
    user_id,
    cookies,
    token,
    client,
    inserted_projects,
    inserted_app_tokens,
    freezer,
):
    """Any user can view only their own single app token at /me/tokens/{id}
    without token itself displayed"""
    # using context manager to ensure on_startup runs
    with client as client:
        token_id = token["_id"]
        url = f"/me/tokens/{token_id}"
        response = client.get(url, cookies=cookies)

        got = response.json()

        expected = {
            "id": token_id,
            "project_id": token["project_id"],
            "title": token["title"],
            "lifespan_seconds": token["lifespan_seconds"],
            "created_at": get_current_timestamp_str(),
        }

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("user_id, cookies, token", _OTHERS_TOKENS_REQUESTS)
def test_view_others_tokens_is_not_allowed(
    user_id,
    cookies,
    token,
    client,
    inserted_projects,
    inserted_app_tokens,
    freezer,
):
    """No user can view only other's app tokens at /me/tokens/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        token_id = token["_id"]
        url = f"/me/tokens/{token_id}"
        response = client.get(url, cookies=cookies)

        got = response.json()
        expected = {"detail": "the token does not exist."}

        assert response.status_code == 404
        assert got == expected


@pytest.mark.parametrize("token", _TOKENS)
def test_extend_own_token_lifespan(
    db,
    token,
    client,
    inserted_projects,
    inserted_app_tokens,
    freezer,
):
    """PUT at /me/tokens/{token_id}, user can update an app token for project they are attached to"""
    lifespan_secs = randint(1000, 300000)
    user_id = token["user_id"]
    cookies = {"some-cookie": get_jwt_token(user_id, ttl=lifespan_secs)}
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=lifespan_secs)
    payload = {
        "lifespan_seconds": 0,
        "title": "foo bar",
        "created_at": "1997-11-25T14:25:47.239Z",
        "id": "anot-p",
        "expires_at": get_timestamp_str(expires_at),
        "project_id": "a-certain-proj",
    }
    # using context manager to ensure on_startup runs
    with client as client:
        token_id = token["_id"]
        url = f"/me/tokens/{token_id}"

        original_token = get_db_record(db, AppToken, token_id)
        response = client.put(url, cookies=cookies, json=payload)

        got = response.json()
        got["lifespan_seconds"] = round(got["lifespan_seconds"])
        expected_response = {
            "id": token_id,
            "project_id": token["project_id"],
            "title": token["title"],
            "lifespan_seconds": lifespan_secs,
            "created_at": get_current_timestamp_str(),
        }
        token_after_update = get_db_record(db, AppToken, token_id)
        token_after_update["lifespan_seconds"] = round(
            token_after_update["lifespan_seconds"]
        )

        assert response.status_code == 200
        assert got == expected_response
        assert token_after_update == {
            **original_token,
            "lifespan_seconds": lifespan_secs,
        }


@pytest.mark.parametrize("token", _TOKENS)
def test_extend_own_expired_token_lifespan(
    db,
    token,
    client,
    inserted_projects,
    app_tokens_with_timestamps,
):
    """Updating expired app tokens raises 404 HTTP error"""
    lifespan_secs = randint(1000, 300000)
    user_id = token["user_id"]
    app_token_ttl = token["lifespan_seconds"]
    cookies = {"some-cookie": get_jwt_token(user_id, ttl=app_token_ttl + lifespan_secs)}
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=lifespan_secs)
    payload = {
        "lifespan_seconds": lifespan_secs + 10000,
        "title": "foo bar",
        "created_at": "1997-11-25T14:25:47.239Z",
        "id": "anot-p",
        "expires_at": expires_at.isoformat("T"),
        "project_id": "a-certain-proj",
    }

    # using context manager to ensure on_startup runs
    with client as client:
        token_id = token["_id"]
        url = f"/me/tokens/{token_id}"
        original_token = get_db_record(db, AppToken, token_id)
        app_token_ttl = token["lifespan_seconds"]

        # shift back the created_at date to a time that would make this token expired
        new_created_at = datetime.now(timezone.utc) - timedelta(
            seconds=app_token_ttl + 1
        )
        update_db_record(
            db,
            AppToken,
            token_id,
            update={"$set": {"created_at": new_created_at}},
        )

        response = client.put(url, cookies=cookies, json=payload)
        token_after_request = get_db_record(db, AppToken, token_id)

        got = response.json()
        expected = {"detail": "Not Found"}

        assert response.status_code == 404
        assert got == expected
        assert original_token is not None
        assert token_after_request is None


@pytest.mark.parametrize("app_token", _TOKENS)
def test_expired_app_token_fails(
    db, app_token, client, inserted_projects, app_tokens_with_timestamps
):
    """Expired app tokens raise 401 HTTP error"""
    token_id = app_token["_id"]
    app_token_ttl = app_token["lifespan_seconds"]
    headers = {"Authorization": f"Bearer {app_token['token']}"}

    # using context manager to ensure on_startup runs
    with client as client:
        # shift back the created_at date to a time that would make this token expired
        new_created_at = datetime.now(timezone.utc) - timedelta(
            seconds=app_token_ttl + 1
        )
        update_db_record(
            db,
            AppToken,
            token_id,
            update={"$set": {"created_at": new_created_at}},
        )

        response = client.get("/jobs/", headers=headers)

        got = response.json()
        expected = {"detail": "Unauthorized"}

        assert response.status_code == 401
        assert got == expected


def test_app_token_of_deleted_user_fails(db, client):
    """An app token whose user is gone raises 401 HTTP error"""
    headers = {"Authorization": f"Bearer {TEST_APP_TOKEN_DICT['token']}"}
    db["auth_users"].delete_one({"_id": ObjectId(TEST_APP_TOKEN_DICT["user_id"])})

    with client as client:
        response = client.get("/jobs/", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_app_token_of_deactivated_user_fails(db, client):
    """An app token whose user is deactivated raises 401 HTTP error"""
    headers = {"Authorization": f"Bearer {TEST_APP_TOKEN_DICT['token']}"}
    db["auth_users"].update_one(
        {"_id": ObjectId(TEST_APP_TOKEN_DICT["user_id"])},
        {"$set": {"is_active": False}},
    )

    with client as client:
        response = client.get("/jobs/", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.parametrize("app_token", _TOKENS)
def test_app_token_of_unallocated_projects_fails(
    app_token, client, unallocated_projects, inserted_app_tokens
):
    """App tokens for projects with qpu_seconds <= 0 raise 403 HTTP error"""
    headers = {"Authorization": f"Bearer {app_token['token']}"}
    project = unallocated_projects[app_token["project_id"]]

    job = {"device": "Loke", "calibration_date": "2024-05-23T09:12:00.733Z"}

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post("/jobs/", json=job, headers=headers)

        got = response.json()
        expected = {
            "detail": f"{float(project['qpu_seconds'])} QPU seconds left on project {project['name']}"
        }

        assert response.status_code == 403
        assert got == expected
