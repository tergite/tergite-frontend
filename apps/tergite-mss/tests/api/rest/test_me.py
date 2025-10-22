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
from typing import List, Optional

import pytest
from pytest_lazyfixture import lazy_fixture

from services.auth import AppToken, Project
from services.auth.projects.dtos import DeletedProject
from tests._utils.auth import (
    TEST_APP_TOKEN_DICT,
    TEST_NO_QPU_APP_TOKEN_DICT,
    TEST_NO_QPU_PROJECT_DICT,
    TEST_PROJECT_DICT,
    TEST_SUPERUSER_DICT,
    TEST_SUPERUSER_EMAIL,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_DICT,
    TEST_USER_DICT,
    TEST_USER_EMAIL,
    TEST_USER_ID,
    get_db_record,
    get_jwt_token,
    update_db_record,
)
from tests._utils.date_time import get_current_timestamp_str, get_timestamp_str
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import insert_in_collection
from tests._utils.records import filter_by_equality, order_by, order_by_many, prune
from tests.conftest import (
    APP_TOKEN_LIST,
    PROJECT_LIST,
    get_auth_cookie,
    get_unauthorized_app_token_post_with_cookies,
)

_JOBS_COLLECTION = "jobs"

_MY_PROJECT_REQUESTS = [
    (user_id, get_auth_cookie(user_id), project)
    for project in PROJECT_LIST
    for user_id in project["user_ids"]
]
_MY_ADMINISTERED_PROJECT_REQUESTS = [
    (project["admin_id"], get_auth_cookie(project["admin_id"]), project)
    for project in PROJECT_LIST
]
_MY_NON_ADMINISTERED_PROJECT_REQUESTS = [
    (user_id, get_auth_cookie(user_id), project)
    for project in PROJECT_LIST
    for user_id in project["user_ids"]
    if user_id != project["admin_id"]
]
_MY_USER_INFO_REQUESTS = [
    (user, get_auth_cookie(str(user["_id"])))
    for user in [TEST_USER_DICT, TEST_SUPERUSER_DICT, TEST_SYSTEM_USER_DICT]
]
_OTHERS_PROJECT_REQUESTS = [
    (user_id, get_auth_cookie(user_id), project)
    for project in PROJECT_LIST
    for user_id in [TEST_USER_ID, TEST_SUPERUSER_ID]
    if user_id not in project["user_ids"]
]

_USER_ID_COOKIES_FIXTURE = [
    (TEST_USER_ID, lazy_fixture("user_jwt_cookie")),
    (TEST_SUPERUSER_ID, lazy_fixture("admin_jwt_cookie")),
]
_MY_TOKENS_REQUESTS = [
    (token["user_id"], get_auth_cookie(token["user_id"]), token)
    for token in APP_TOKEN_LIST
]
_OTHERS_TOKENS_REQUESTS = [
    (user_id, get_auth_cookie(user_id), token)
    for token in APP_TOKEN_LIST
    for user_id in [TEST_USER_ID, TEST_SUPERUSER_ID]
    if user_id != token["user_id"]
]
_EXTRA_PROJECT_DEFAULTS = {
    "resource_ids": [],
    "source": "internal",
    "user_emails": None,
    "admin_email": None,
}
_SKIP_LIMIT_SORT_PARAMS = [
    (0, 1, ["-job_id", "created_at"]),
    (1, 4, None),
    (2, None, ["created_at"]),
]
_SEARCH_PARAMS = [
    {"device": "Loke"},
    {"device": "Pingu", "status": "successful"},
    {"status": "failed"},
    {},
    {"project_id": "653a8f19e736d76276597a6c"},
    {"project_id": "653a8f19e736d76276597a6c", "status": "pending"},
]
_PAGINATE_AND_SEARCH_PARAMS = [
    (skip, limit, sort, search, user_id, cookie)
    for skip, limit, sort in _SKIP_LIMIT_SORT_PARAMS
    for search in _SEARCH_PARAMS
    for user_id, cookie in _USER_ID_COOKIES_FIXTURE
]


_JOBS_LIST_IN_DB = load_json_fixture("my_jobs_in_db.json")
_JOBS_LIST_AS_RESPONSES = load_json_fixture("my_job_responses.json")


@pytest.mark.parametrize("user_id, cookies", _USER_ID_COOKIES_FIXTURE)
def test_view_own_projects_in_less_detail(
    user_id, cookies, client, inserted_project_ids
):
    """Any user can view only their own projects at /me/projects/
    without user_ids"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/me/projects/", cookies=cookies)

        got = response.json()
        project_list = [
            {
                "id": str(item["_id"]),
                "name": item.get("name", None),
                "ext_id": item["ext_id"],
                "qpu_seconds": item["qpu_seconds"],
                "description": item.get("description", None),
                "user_ids": item.get("user_ids", None),
                "admin_id": item.get("admin_id", None),
                "is_active": item.get("is_active", True),
                "created_at": item.get("created_at", None),
                "updated_at": item.get("updated_at", None),
            }
            for item in [TEST_PROJECT_DICT, TEST_NO_QPU_PROJECT_DICT] + PROJECT_LIST
            if user_id in item["user_ids"]
        ]

        assert response.status_code == 200
        assert got == {"skip": 0, "limit": None, "data": project_list}


@pytest.mark.parametrize("user_id, cookies, project", _MY_PROJECT_REQUESTS)
def test_view_my_project_in_less_detail(
    user_id, cookies, project, client, inserted_projects
):
    """Any user can view only their own single project at /me/projects/{id}
    without user_emails"""
    # using context manager to ensure on_startup runs
    with client as client:
        project_id = project["_id"]
        url = f"/me/projects/{project_id}"
        response = client.get(url, cookies=cookies)

        got = response.json()
        expected = {
            "id": project_id,
            "name": project["name"],
            "ext_id": project["ext_id"],
            "qpu_seconds": project["qpu_seconds"],
            "description": project["description"],
            "user_ids": project["user_ids"],
            "admin_id": project["admin_id"],
            "is_active": project.get("is_active", True),
            "created_at": project["created_at"],
            "updated_at": project["updated_at"],
        }

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("user_id, cookies, project", _OTHERS_PROJECT_REQUESTS)
def test_view_others_project_is_not_allowed(
    user_id, cookies, project, client, inserted_projects
):
    """No user can view other's projects at /me/projects/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        project_id = project["_id"]
        url = f"/me/projects/{project_id}"
        response = client.get(url, cookies=cookies)

        got = response.json()
        expected = {"detail": "the project does not exist."}

        assert response.status_code == 404
        assert got == expected


@pytest.mark.parametrize("user_id, cookies, project", _MY_ADMINISTERED_PROJECT_REQUESTS)
def test_delete_own_project(
    user_id, cookies, project, client, inserted_projects, db, freezer
):
    """Any user can delete the project they administer at /me/projects/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        _id = project["_id"]
        url = f"/me/projects/{_id}"

        now = get_current_timestamp_str()
        original = get_db_record(db, Project, _id)
        assert original is not None
        response = client.delete(url, cookies=cookies)

        deleted_project = get_db_record(db, DeletedProject, _id)
        pruned_fields = ["created_at", "updated_at"]
        pruned_deleted_project, deleted_project_timestamps = prune(
            deleted_project, pruned_fields
        )
        pruned_original, _ = prune(original, pruned_fields)
        pruned_original.update(_EXTRA_PROJECT_DEFAULTS)

        assert response.status_code == 204
        assert get_db_record(db, Project, _id) is None
        assert pruned_deleted_project == pruned_original
        for timestamp in deleted_project_timestamps.values():
            assert timestamp == now


@pytest.mark.parametrize(
    "user_id, cookies, project", _MY_NON_ADMINISTERED_PROJECT_REQUESTS
)
def test_delete_others_project_is_not_allowed(
    user_id, cookies, project, client, inserted_projects, db
):
    """No user can delete projects they don't administer at /me/projects/{id}"""
    # using context manager to ensure on_startup runs
    with client as client:
        project_id = project["_id"]
        url = f"/me/projects/{project_id}"

        assert get_db_record(db, Project, project_id) is not None
        response = client.delete(url, cookies=cookies)

        got = response.json()
        expected = {"detail": "Forbidden"}

        assert response.status_code == 403
        assert got == expected
        assert get_db_record(db, Project, project_id) is not None


@pytest.mark.parametrize("payload", APP_TOKEN_LIST)
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


@pytest.mark.parametrize("payload", APP_TOKEN_LIST)
def test_unauthenticated_app_token_generation(payload, inserted_projects, client):
    """401 error raised at /me/tokens/ when no user jwt is sent"""

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post("/me/tokens/", json=payload)

        got = response.json()
        expected = {"detail": "Unauthorized"}
        assert response.status_code == 401
        assert got == expected


@pytest.mark.parametrize(
    "body, cookies", get_unauthorized_app_token_post_with_cookies()
)
def test_unauthorized_app_token_generation(body, cookies, inserted_projects, client):
    """403 error raised at /me/tokens/, for a project to which a user is not attached"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post("/me/tokens/", cookies=cookies, json=body)

        got = response.json()
        expected = {"detail": "Forbidden"}
        assert response.status_code == 403
        assert got == expected


@pytest.mark.parametrize("payload", APP_TOKEN_LIST)
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


@pytest.mark.parametrize("payload", APP_TOKEN_LIST)
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
        update_obj = {"$set": {"created_at": new_created_at.isoformat(sep="T")}}
        update_db_record(db, AppToken, _id, update=update_obj)

        url = f"/me/tokens/{_id}"
        cookies = get_auth_cookie(user_id)
        response = client.delete(url, cookies=cookies)

        assert response.status_code == 204
        assert get_db_record(db, AppToken, _id) is None


@pytest.mark.parametrize("payload", APP_TOKEN_LIST)
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


@pytest.mark.parametrize(
    "payload, cookies", get_unauthorized_app_token_post_with_cookies()
)
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
                "project_ext_id": v["project_ext_id"],
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
            "project_ext_id": token["project_ext_id"],
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


@pytest.mark.parametrize("token", APP_TOKEN_LIST)
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
        "project_ext_id": "a-certain-proj",
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
            "project_ext_id": token["project_ext_id"],
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


@pytest.mark.parametrize("token", APP_TOKEN_LIST)
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
        "project_ext_id": "a-certain-proj",
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
            update={"$set": {"created_at": new_created_at.isoformat(sep="T")}},
        )

        response = client.put(url, cookies=cookies, json=payload)
        token_after_request = get_db_record(db, AppToken, token_id)

        got = response.json()
        expected = {"detail": "Not Found"}

        assert response.status_code == 404
        assert got == expected
        assert original_token is not None
        assert token_after_request is None


@pytest.mark.parametrize("app_token", APP_TOKEN_LIST)
def test_expired_app_token_fails(
    db, app_token, client, inserted_projects, app_tokens_with_timestamps
):
    """Expired app tokens raise 401 HTTP error"""
    token_id = app_token["_id"]
    app_token_ttl = app_token["lifespan_seconds"]
    cookies = {"some-token": app_token["token"]}

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
            update={"$set": {"created_at": new_created_at.isoformat(sep="T")}},
        )

        response = client.get("/", cookies=cookies)

        got = response.json()
        expected = {"detail": "Unauthorized"}

        assert response.status_code == 401
        assert got == expected


@pytest.mark.parametrize("app_token", APP_TOKEN_LIST)
def test_app_token_of_unallocated_projects_fails(
    app_token, client, unallocated_projects, inserted_app_tokens
):
    """App tokens for projects with qpu_seconds <= 0 raise 403 HTTP error"""
    headers = {"Authorization": f"Bearer {app_token['token']}"}
    project = unallocated_projects[app_token["project_ext_id"]]

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/", headers=headers)

        got = response.json()
        expected = {
            "detail": f"{float(project['qpu_seconds'])} QPU seconds left on project {project['ext_id']}"
        }

        assert response.status_code == 403
        assert got == expected


@pytest.mark.parametrize(
    "skip, limit, sort, search, user_id, cookies", _PAGINATE_AND_SEARCH_PARAMS
)
def test_find_my_jobs(
    db,
    client,
    skip: Optional[int],
    limit: Optional[int],
    sort: Optional[List[str]],
    search: dict,
    user_id,
    cookies,
):
    """Get to /me/job/?project_id=...&device=... can search for the jobs that fulfill the given filters"""
    insert_in_collection(
        database=db, collection_name=_JOBS_COLLECTION, data=_JOBS_LIST_IN_DB
    )

    query_string = "?"
    slice_end = len(_JOBS_LIST_IN_DB)
    slice_start = 0
    sort_fields = [
        "-created_at",
    ]
    if limit is not None:
        query_string += f"limit={limit}&"
        slice_end = limit
    if skip is not None:
        query_string += f"skip={skip}&"
        slice_start = skip
        slice_end += skip
    if sort is not None:
        sort_fields = sort
        for sort_field in sort_fields:
            query_string += f"sort={sort_field}&"

    # Adding search
    for key, value in search.items():
        query_string += f"{key}={value}&"

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(f"/me/jobs/{query_string}", cookies=cookies)
        got = response.json()
        effective_filters = {**search, "user_id": user_id}
        filtered_data = filter_by_equality(
            _JOBS_LIST_AS_RESPONSES, filters=effective_filters
        )
        sorted_data = order_by_many(filtered_data, fields=sort_fields)
        expected = {
            "skip": slice_start,
            "limit": limit,
            "data": sorted_data[slice_start:slice_end],
        }

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("user, cookies", _MY_USER_INFO_REQUESTS)
def test_view_my_user_info(user, cookies, client):
    """Any user can view only their own single user information at /me"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/me", cookies=cookies)

        raw_data = response.json()
        got = {**raw_data, "roles": sorted(raw_data.get("roles", []))}
        expected = {
            "id": str(user["_id"]),
            "email": user["email"],
            "is_active": user.get("is_active", True),
            "is_verified": user.get("is_verified", False),
            "is_superuser": user.get("is_superuser", False),
            "roles": sorted(user.get("roles", [])),
        }

        assert response.status_code == 200
        assert got == expected


# @pytest.mark.parametrize("client, redis_conn, worker, job", _SIMPLE_UPLOAD_JOB_PARAMS)
# def test_delete_profile(
#     client, worker, redis_conn, job, jobs_folder, mocker: MockerFixture
# ):
#     """DELETE '/me' should delete their own user profile"""
#     with client as client:
#         users = _create_many_users(client, USERS[:2])
#         curr_user = users[0]
#         other_user = users[1]
#
#         curr_user_id = curr_user["id"]
#         other_user_id = other_user["id"]
#
#         # create many bookings for this user
#         for booking in VALID_BOOKINGS[:TEST_MAX_SLOTS_PER_DAY]:
#             _create_booking(client, user_id=curr_user_id, booking=booking)
#
#         # create a booking for other user
#         _create_booking(
#             client, user_id=other_user_id, booking={"starts_in": 8, "duration": 2}
#         )
#
#         # wait for the first booking to start
#         raw_jobs = _get_raw_jobs(job, durations=[0.23, 0.1, 0.23])
#         job_metadata_list = _get_job_submission_metadata(
#             client, jobs=raw_jobs, users=users, mocker=mocker, jobs_folder=jobs_folder
#         )
#         _submit_multiple_jobs_v2(client, data=job_metadata_list)
#
#         # This should also cancel any bookings and any jobs belonging to user
#         response = _delete_own_profile(client, user_id=curr_user_id)
#         assert response.status_code == 200
#         assert response.json() == {"status": "success", "detail": "Profile deleted"}
#
#         response = _view_own_profile(client, user_id=curr_user_id)
#         assert response.status_code == 404
#         assert response.json() == {"detail": "user not found"}
#
#         # Run the queue; try to wait for waitlist to transfer things to execution queue
#         _wait_on_rq_worker(worker, with_scheduler=True)
#
#         jobs_in_redis = _get_jobs_in_redis(redis_conn)
#
#         deleted_user_jobs = [
#             job for job in jobs_in_redis if job.user_id == curr_user_id
#         ]
#         other_user_jobs = [job for job in jobs_in_redis if job.user_id != curr_user_id]
#         failure_reason = "Cancelled on user deletion"
#
#         assert all([v.status == JobStatus.CANCELLED for v in deleted_user_jobs])
#         assert all([v.failure_reason == failure_reason for v in deleted_user_jobs])
#         assert all([v.status == JobStatus.SUCCESSFUL for v in other_user_jobs])
