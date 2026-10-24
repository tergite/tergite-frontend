# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023, 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Integration tests for the jobs router"""
import copy
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import pytest
from pytest_lazyfixture import lazy_fixture
from pytest_mock import MockerFixture

import settings
from libs.storage import generate_id
from services.auth import AppToken, Project
from services.jobs import Job
from services.notices import Notice, NoticeSeverity, NoticeType
from tests._utils.auth import (
    TEST_PROJECT_ID,
    TEST_PROJECT_NAME,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_ID,
    TEST_USER_ID,
)
from tests._utils.bcc import create_bcc_headers
from tests._utils.date_time import (
    get_current_timestamp_str,
)
from tests._utils.env import TEST_BACKENDS_MAP
from tests._utils.fixtures import load_json_fixture
from tests._utils.notices import get_user_notices
from tests._utils.records import (
    filter_by_equality,
    order_by_many,
    prune,
    with_current_timestamps,
    with_incremental_timestamps,
)
from tests._utils.storage import insert_if_not_exist, to_record

_JOBS_LIST = load_json_fixture("job_list.json")
_JOB_BCC_TOKEN_MAP: Dict[str, dict] = load_json_fixture("bcc_jwt_tokens.json")
_JOB_TIMESTAMPED_UPDATES = load_json_fixture("job_timestamped_updates.json")
_JOB_UPDATES = load_json_fixture("job_updates.json")
_JOB_IDS = [item["job_id"] for item in _JOBS_LIST]
_DEVICES = ["Loke", "Loki", "Pingu"]
_CREATE_JOB_PAYLOADS = [
    (
        {
            "device": device,
            "calibration_date": (
                "2024-05-23T09:12:00.733Z"
                if idx % 2 == 0
                else "2025-04-23T09:12:00.743Z"
            ),
        }
    )
    for idx, device in enumerate(_DEVICES)
]
_UNAVAILABLE_BCC_FIXTURE = [
    ({"device": device, "calibration_date": "2024-05-23T09:12:00.733Z"}, client)
    for device in _DEVICES[:1]
    for client in (
        lazy_fixture("mock_timed_out_bcc"),
        lazy_fixture("mock_unavailable_bcc"),
    )
]
_SKIP_LIMIT_SORT_PARAMS = [
    (0, 1, ["-job_id", "created_at"]),
    (2, 4, None),
    (4, 6, ["job_id"]),
    (None, 10, None),
    (3, None, ["created_at"]),
]
_SEARCH_PARAMS = [
    {"device": "Loke"},
    {"device": "Pingu"},
    {"device": "Pingu", "status": "successful"},
    {"device": "Pingu", "status": "pending"},
    {"status": "successful"},
    {"status": "pending"},
    {},
]
# paging and searching are independent, so each is tested without the other
_PAGINATE_AND_SEARCH_PARAMS = [
    *((skip, limit, sort, {}) for skip, limit, sort in _SKIP_LIMIT_SORT_PARAMS),
    *((None, None, None, search) for search in _SEARCH_PARAMS if search),
]
# one job of each shape: with and without a BCC token, a status, a result, a device,
# and fields the job does not have
_READ_JOB_IDS = [_JOB_IDS[0], _JOB_IDS[3]]
_JOB_UPDATES_OF_EACH_SHAPE = [_JOB_UPDATES[i] for i in (0, 1, 3, 4, 5, 9, 10)]
_DEVICES_AND_JOB_UPDATES = [
    *((_DEVICES[0], job_update) for job_update in _JOB_UPDATES_OF_EACH_SHAPE),
    (_DEVICES[1], _JOB_UPDATES[0]),
]
# the first with a result, the last with a status alone
_DEVICES_AND_JOB_TIMESTAMPED_UPDATES = [
    (_DEVICES[0], _JOB_TIMESTAMPED_UPDATES[0]),
    (_DEVICES[0], _JOB_TIMESTAMPED_UPDATES[-1]),
    (_DEVICES[1], _JOB_TIMESTAMPED_UPDATES[0]),
]
_BILLED_JOB_UPDATE = _JOB_TIMESTAMPED_UPDATES[0]
_BILLED_JOB_COST = (
    datetime.fromisoformat(_BILLED_JOB_UPDATE["timestamps"]["execution"]["finished"])
    - datetime.fromisoformat(_BILLED_JOB_UPDATE["timestamps"]["execution"]["started"])
).total_seconds()
_QPU_THRESHOLD = settings.CONFIG.projects.qpu_seconds_low_threshold


@pytest.mark.parametrize("job_id", _READ_JOB_IDS)
def test_read_job(db, client, job_id: str, no_qpu_app_token_header, freezer):
    """Get to /jobs/{job_id} returns the job for the given job_id"""
    all_jobs = with_current_timestamps(
        _JOBS_LIST, fields=("created_at", "updated_at", "calibration_date")
    )
    all_jobs = _with_bcc_tokens(all_jobs)
    expected = _get_job(all_jobs, job_id=job_id)
    if job_id in _JOB_BCC_TOKEN_MAP:
        expected["access_token"] = _JOB_BCC_TOKEN_MAP[job_id]["plain"]

    _insert_jobs(db, all_jobs)

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(f"/jobs/{job_id}", headers=no_qpu_app_token_header)
        got = response.json()

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("path", ["/jobs/{job_id}", "/jobs/{job_id}/status"])
def test_read_another_users_job_is_not_found(db, client, app_token_header, path):
    """Get /jobs/{job_id} hides a job another user submitted"""
    job = {**_prepare_jobs()[0], "user_id": TEST_SYSTEM_USER_ID}
    _insert_jobs(db, [job])

    with client as client:
        response = client.get(path.format(**job), headers=app_token_header)

    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/jobs/{job_id}", "/jobs/{job_id}/status"])
def test_read_own_job(db, client, app_token_header, path):
    """Get /jobs/{job_id} returns a job the token's user submitted"""
    job = {**_prepare_jobs()[0], "user_id": TEST_USER_ID}
    _insert_jobs(db, [job])

    with client as client:
        response = client.get(path.format(**job), headers=app_token_header)

    assert response.status_code == 200


def test_admin_reads_another_users_job(db, client):
    """Get /jobs/{job_id} returns any user's job to an admin"""
    job = {**_prepare_jobs()[0], "user_id": TEST_USER_ID}
    _insert_jobs(db, [job])
    headers = _insert_superuser_app_token(db)

    with client as client:
        response = client.get(f"/jobs/{job['job_id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["job_id"] == job["job_id"]


def test_list_jobs_shows_own_and_unowned_jobs(db, client, app_token_header):
    """Get /jobs/ leaves out jobs other users submitted"""
    own, others, unowned = (
        {**_prepare_jobs()[0], "user_id": TEST_USER_ID},
        {**_prepare_jobs()[1], "user_id": TEST_SYSTEM_USER_ID},
        {**_prepare_jobs()[2], "user_id": None},
    )
    _insert_jobs(db, [own, others, unowned])

    with client as client:
        response = client.get("/jobs/", headers=app_token_header)

    job_ids = {job["job_id"] for job in response.json()["data"]}
    assert response.status_code == 200
    assert job_ids == {own["job_id"], unowned["job_id"]}


@pytest.mark.parametrize("payload", _CREATE_JOB_PAYLOADS)
def test_create_job(
    mock_bcc,
    db,
    client,
    payload,
    project_id: str,
    app_token_header,
    current_user_id,
    freezer,
    mocker: MockerFixture,
):
    """Post to /jobs/ creates a job in the given backend"""
    import base64

    import jwt

    jwt_encode_spy = mocker.spy(jwt, "encode")
    base64_b64encode_spy = mocker.spy(base64, "b64encode")

    device = payload["device"]
    device_url = TEST_BACKENDS_MAP[device]["url"]
    expected_bcc_base_url = TEST_BACKENDS_MAP[device].get("public_url", device_url)
    jobs_before_creation = _get_stored_jobs(db)
    timestamp = get_current_timestamp_str()

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post("/jobs/", json=payload, headers=app_token_header)
        json_response = response.json()
        new_job_id = json_response["job_id"]
        jobs_after_creation = _get_stored_jobs(db)
        plain_token = jwt_encode_spy.spy_return
        encrypted_token_bytes = base64_b64encode_spy.spy_return
        encrypted_token = encrypted_token_bytes.decode()

        mocker.stop(jwt_encode_spy)
        mocker.stop(base64_b64encode_spy)

        expected_job = {
            "project_id": project_id,
            "job_id": new_job_id,
            "user_id": current_user_id,
            "device": device,
            "status": "pending",
            "calibration_date": payload["calibration_date"],
            "updated_at": timestamp,
            "created_at": timestamp,
            "access_token": encrypted_token,
        }

        assert response.status_code == 200
        assert response.json() == {
            "job_id": str(new_job_id),
            "upload_url": f"{expected_bcc_base_url}/jobs",
            "access_token": plain_token,
        }

        assert jobs_before_creation == []
        assert jobs_after_creation == [_get_job_values(expected_job)]


@pytest.mark.parametrize("payload, bcc", _UNAVAILABLE_BCC_FIXTURE)
def test_create_job_without_bcc(db, client, payload, app_token_header, bcc):
    """Post to /jobs/ error out if BCC is not available"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post("/jobs/", json=payload, headers=app_token_header)
        jobs_after_creation = _get_stored_jobs(db)

        assert response.status_code == 503
        assert response.json() == {"detail": "device is currently unavailable"}
        # no job created
        assert jobs_after_creation == []


@pytest.mark.parametrize("payload", _CREATE_JOB_PAYLOADS[:1])
def test_create_job_with_invalid_request_id(db, client, payload, app_token_header):
    """Post to /jobs/ with an x-request-id that is not a UUID4 is a bad request"""
    headers = {**app_token_header, "x-request-id": "not-a-uuid"}

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post("/jobs/", json=payload, headers=headers)

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The request ID 'not-a-uuid' is not a valid UUID4"
    }


@pytest.mark.parametrize("skip, limit, sort, search", _PAGINATE_AND_SEARCH_PARAMS)
def test_find_jobs(
    db,
    client,
    skip: Optional[int],
    limit: Optional[int],
    sort: Optional[List[str]],
    search: dict,
    no_qpu_app_token_header,
    freezer,
):
    """Get to /job/?project_id=...&device=... can search for the jobs that fulfill the given filters"""
    raw_jobs = with_incremental_timestamps(
        _JOBS_LIST,
        fields=(
            "created_at",
            "updated_at",
            "calibration_date",
        ),
    )
    _insert_jobs(db, raw_jobs)

    query_string = "?"
    slice_end = len(raw_jobs)
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
        response = client.get(f"/jobs/{query_string}", headers=no_qpu_app_token_header)
        got = response.json()
        filtered_data = filter_by_equality(raw_jobs, filters=search)
        sorted_data = order_by_many(filtered_data, fields=sort_fields)
        expected = {
            "skip": slice_start,
            "limit": limit,
            "data": sorted_data[slice_start:slice_end],
        }

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("device, raw_payload", _DEVICES_AND_JOB_UPDATES)
def test_update_job(db, client, device: str, raw_payload: dict, freezer):
    """Pushing 'job_updated'-DeviceEvent to /devices/ws/{name} updates the job with the given object"""
    job_id = raw_payload["job_id"]
    raw_jobs = with_incremental_timestamps(
        _JOBS_LIST, fields=["created_at", "calibration_date"]
    )
    raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])

    raw_jobs = _with_bcc_tokens(raw_jobs)
    expected_job = _get_job(raw_jobs, job_id=job_id)
    expected_response = copy.deepcopy(expected_job)
    if job_id in _JOB_BCC_TOKEN_MAP:
        expected_response["access_token"] = _JOB_BCC_TOKEN_MAP[job_id]["plain"]

    _insert_jobs(db, raw_jobs)

    ignored_fields = ["unexpected_field", "random_field"]

    url = f"/devices/ws/{device}"
    headers = create_bcc_headers(device)

    # using context manager to ensure on_startup runs
    with client as client:
        with client.websocket_connect(url, headers=headers) as client:
            event_id = str(uuid.uuid4())
            client.send_json(
                {
                    "id": event_id,
                    "name": "job_updated",
                    "data": raw_payload,
                }
            )
            response = client.receive_json()
            got = response["data"]

            actual_update, _ = prune(raw_payload, ignored_fields)
            expected_job.update(
                actual_update,
            )
            expected_response.update(
                actual_update,
            )

            job_after_update = _get_stored_jobs(db, {"job_id": job_id})[0]

            assert response["status"] == "success"
            assert got == expected_response
            assert job_after_update == _get_job_values(expected_job)


@pytest.mark.parametrize("device, raw_payload", _DEVICES_AND_JOB_TIMESTAMPED_UPDATES)
def test_update_job_resource_usage(
    db, client, project_id, device: str, raw_payload: dict, freezer
):
    """Pushing 'job_updated' event to /devices/ws/{name} updates the job's resource usage if passed with 'timestamps' field"""
    raw_jobs = with_incremental_timestamps(
        _JOBS_LIST, fields=["created_at", "calibration_date"]
    )
    raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])
    job_list = [{**item, "project_id": str(project_id)} for item in raw_jobs]

    _insert_jobs(db, job_list)

    project_before_update = db.get(Project, TEST_PROJECT_ID)

    url = f"/devices/ws/{device}"
    headers = create_bcc_headers(device)

    # using context manager to ensure on_startup runs
    with client as client:
        with client.websocket_connect(url, headers=headers) as client:
            event_id = str(uuid.uuid4())
            client.send_json(
                {
                    "id": event_id,
                    "name": "job_updated",
                    "data": raw_payload,
                }
            )
            response = client.receive_json()
            assert response["status"] == "success"

    project_after_update = db.get(Project, TEST_PROJECT_ID)
    expected_resource_usage = _get_resource_usage(raw_payload["timestamps"])
    actual_resource_usage = round(
        project_before_update.qpu_seconds - project_after_update.qpu_seconds, 1
    )

    assert actual_resource_usage == expected_resource_usage


@pytest.mark.parametrize("device, payload", _DEVICES_AND_JOB_TIMESTAMPED_UPDATES)
def test_update_job_resource_usage_advanced(
    db, client, project_id, device: str, payload: dict, freezer
):
    """Pushing 'job_updated' event to /devices/ws/{name} updates the job's resource usage if passed with "timestamps.execution" field"""
    raw_jobs = with_incremental_timestamps(
        _JOBS_LIST, fields=["created_at", "calibration_date"]
    )
    raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])
    job_list = [{**item, "project_id": str(project_id)} for item in raw_jobs]
    _insert_jobs(db, job_list)

    project_before_update = db.get(Project, TEST_PROJECT_ID)

    url = f"/devices/ws/{device}"
    headers = create_bcc_headers(device)

    # using context manager to ensure on_startup runs
    with client as client:
        with client.websocket_connect(url, headers=headers) as client:
            event_id = str(uuid.uuid4())
            client.send_json(
                {
                    "id": event_id,
                    "name": "job_updated",
                    "data": payload,
                }
            )
            response = client.receive_json()
            assert response["status"] == "success"

    project_after_update = db.get(Project, TEST_PROJECT_ID)
    expected_resource_usage = _get_resource_usage(payload["timestamps"])
    actual_resource_usage = round(
        project_before_update.qpu_seconds - project_after_update.qpu_seconds, 1
    )

    assert actual_resource_usage == expected_resource_usage


@pytest.mark.parametrize("job", _JOBS_LIST[:2])
def test_cancel_job(db, client, user_jwt_cookie, job, mock_bcc, freezer):
    """A POST to '/jobs/{id}/cancel' cancels the job of the job_id if the job belongs to the current user"""
    with client as client:
        raw_jobs = with_incremental_timestamps(
            [job], fields=["created_at", "calibration_date"]
        )
        raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])
        user_id = TEST_USER_ID
        raw_jobs = [{**item, "user_id": user_id} for item in raw_jobs]
        job_info = raw_jobs[0]
        job_id = job_info["job_id"]
        cancellation_reason = "just testing"

        _insert_jobs(db, raw_jobs)

        response = client.post(
            f"/jobs/{job_id}/cancel",
            json={"reason": cancellation_reason},
            cookies=user_jwt_cookie,
        )
        got = response.json()
        job_in_db = _get_stored_jobs(db, {"job_id": job_id})[0]

        assert response.status_code == 200
        assert got == {
            "status": "success",
            "detail": f"Job of id {job_id} cancelled",
        }

        assert job_in_db == _get_job_values(
            {
                **job_info,
                "status": "cancelled",
                "cancellation_reason": cancellation_reason,
            }
        )


@pytest.mark.parametrize("job", _JOBS_LIST[:1])
def test_unauthenticated_cancel_job(db, client, job, mock_bcc, freezer):
    """POST to `/jobs/{job_id}/cancel` raises 401 if not accessed with an authentic cookie"""
    with client as client:
        raw_jobs = with_incremental_timestamps(
            [job], fields=["created_at", "calibration_date"]
        )
        raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])
        user_id = TEST_USER_ID
        raw_jobs = [{**item, "user_id": user_id} for item in raw_jobs]
        job_info = raw_jobs[0]
        job_id = job_info["job_id"]
        cancellation_reason = "just testing"

        _insert_jobs(db, raw_jobs)

        payload = {"reason": cancellation_reason}
        url = f"/jobs/{job_id}/cancel"

        response = client.post(url, json=payload)
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

        invalid_headers = {"Auhtorization": "Bearer some-wrong-token"}
        response = client.post(url, headers=invalid_headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.parametrize("idx", range(2))
def test_remove_job(db, client, user_jwt_cookie, idx: int, mock_bcc, freezer):
    """DELETE to '/jobs/{job_id}' deletes the given job if job belongs to user"""
    # using context manager to ensure on_startup runs
    with client as client:
        raw_jobs = with_incremental_timestamps(
            _JOBS_LIST[:4], fields=["created_at", "calibration_date"]
        )
        raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])
        user_id = TEST_USER_ID
        raw_jobs = [{**item, "user_id": user_id} for item in raw_jobs]
        job_id = raw_jobs[idx]["job_id"]

        _insert_jobs(db, raw_jobs)

        response = client.delete(f"/jobs/{job_id}", cookies=user_jwt_cookie)
        got = response.json()
        jobs_in_db = _get_stored_jobs(db)
        expected_jobs = [item for item in raw_jobs if item["job_id"] != job_id]

        assert response.status_code == 200
        assert got == {
            "status": "success",
            "detail": f"Job of id {job_id} deleted",
        }

        assert jobs_in_db == [_get_job_values(job) for job in expected_jobs]


@pytest.mark.parametrize("idx", range(1))
def test_unauthenticated_remove_job(db, client, idx: int, mock_bcc, freezer):
    """Delete to /jobs/{job_id} returns 401 error when accessed outside MSS or without proper MSS headers"""
    # using context manager to ensure on_startup runs
    with client as client:
        raw_jobs = with_incremental_timestamps(
            _JOBS_LIST[:4], fields=["created_at", "calibration_date"]
        )
        raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])
        user_id = TEST_USER_ID
        raw_jobs = [{**item, "user_id": user_id} for item in raw_jobs]
        job_id = raw_jobs[idx]["job_id"]

        _insert_jobs(db, raw_jobs)

        response = client.delete(f"/jobs/{job_id}")
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

        invalid_headers = {"Auhtorization": "Bearer some-wrong-token"}
        response = client.delete(f"/jobs/{job_id}", headers=invalid_headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


def test_dropping_below_the_qpu_threshold_warns_the_project_admin(client, db):
    """The person who can request more QPU time is the one told the project runs low"""
    start = _QPU_THRESHOLD + _BILLED_JOB_COST - 1

    _bill_a_job(client, db, starting_seconds=start)
    admin_notices = get_user_notices(db, TEST_USER_ID)

    assert db.get(Project, TEST_PROJECT_ID).qpu_seconds == (
        pytest.approx(start - _BILLED_JOB_COST)
    )
    assert [item.type for item in admin_notices] == [NoticeType.QPU_SECONDS_LOW.id]
    assert admin_notices[0].title == (f"{TEST_PROJECT_NAME} is running low on QPU time")
    assert admin_notices[0].body == (
        f"{TEST_PROJECT_NAME} has {_QPU_THRESHOLD - 1:.0f}s of QPU time left. "
        "Request more before it runs out."
    )
    assert admin_notices[0].severity == NoticeSeverity.WARNING
    assert get_user_notices(db, TEST_SYSTEM_USER_ID) == []


def test_staying_above_the_qpu_threshold_warns_nobody(client, db):
    """A project with plenty of QPU time left is not worth interrupting anyone over"""
    _bill_a_job(client, db, starting_seconds=_QPU_THRESHOLD + _BILLED_JOB_COST * 10)

    assert db.count(Notice) == 0


def test_a_second_job_below_the_qpu_threshold_does_not_warn_again(client, db):
    """Only the job that crosses the threshold warns, not every job after it"""
    _bill_a_job(client, db, starting_seconds=_QPU_THRESHOLD + _BILLED_JOB_COST - 1)
    db.delete_many(Job, {})

    _bill_a_job(client, db, starting_seconds=_QPU_THRESHOLD - 1)

    assert [item.type for item in get_user_notices(db, TEST_USER_ID)] == [
        NoticeType.QPU_SECONDS_LOW.id
    ]


def test_running_out_of_qpu_time_tells_all_members(client, db):
    """Members cannot request more time, but they need to know why their jobs stopped"""
    _bill_a_job(client, db, starting_seconds=1)
    depleted_notices = db.find(Notice, {"type": NoticeType.QPU_SECONDS_DEPLETED.id})

    assert {item.user_id for item in depleted_notices} == {
        TEST_USER_ID,
        TEST_SYSTEM_USER_ID,
    }
    assert {item.severity for item in depleted_notices} == {NoticeSeverity.CRITICAL}


def test_running_out_of_qpu_time_after_running_low(client, db):
    """Running out is reported even when running low was reported before"""
    _bill_a_job(client, db, starting_seconds=_QPU_THRESHOLD + _BILLED_JOB_COST - 1)
    db.delete_many(Job, {})

    _bill_a_job(client, db, starting_seconds=1)

    assert [item.type for item in get_user_notices(db, TEST_USER_ID)] == [
        NoticeType.QPU_SECONDS_LOW.id,
        NoticeType.QPU_SECONDS_DEPLETED.id,
    ]


def test_an_already_empty_project_does_not_warn_again(client, db):
    """Only the job that uses up the last QPU time reports it"""
    _bill_a_job(client, db, starting_seconds=-5)

    assert db.count(Notice) == 0


def _bill_a_job(client, db, starting_seconds: Optional[float] = None):
    """Runs a job of the test project to completion, optionally setting its QPU time first

    Args:
        client: the test client
        db: the database
        starting_seconds: the QPU seconds to start from; None leaves them as they are
    """
    raw_jobs = with_incremental_timestamps(
        _JOBS_LIST, fields=["created_at", "calibration_date"]
    )
    raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])
    _insert_jobs(db, [{**item, "project_id": TEST_PROJECT_ID} for item in raw_jobs])
    if starting_seconds is not None:
        db.update_one(
            Project,
            {"id": TEST_PROJECT_ID},
            {"$set": {"qpu_seconds": starting_seconds}},
        )

    device = _DEVICES[0]
    with client as client:
        with client.websocket_connect(
            f"/devices/ws/{device}", headers=create_bcc_headers(device)
        ) as socket:
            socket.send_json(
                {
                    "id": str(uuid.uuid4()),
                    "name": "job_updated",
                    "data": _BILLED_JOB_UPDATE,
                }
            )
            assert socket.receive_json()["status"] == "success"


def _get_resource_usage(timestamps: Dict[str, Dict[str, str]]) -> Optional[float]:
    """Retrieves the resource usage in seconds"""
    try:
        execution_timestamps = timestamps["execution"]
        started_timestamp_str = execution_timestamps["started"].replace("Z", "+00:00")
        finished_timestamp_str = execution_timestamps["finished"].replace("Z", "+00:00")
        started_timestamp = datetime.fromisoformat(started_timestamp_str)
        finished_timestamp = datetime.fromisoformat(finished_timestamp_str)
        return round((finished_timestamp - started_timestamp).total_seconds(), 1)
    except AttributeError:
        return 0


def _with_bcc_tokens(data: List[dict]) -> List[dict]:
    """Returns the list of records with access_tokens added basing on the _JOB_BCC_TOKEN_MAP

    Args:
        data: the list of the job records

    Returns:
        the list of the updated records
    """
    return [
        item
        if item["job_id"] not in _JOB_BCC_TOKEN_MAP
        else {**item, "access_token": _JOB_BCC_TOKEN_MAP[item["job_id"]]["encrypted"]}
        for item in data
    ]


def _get_job(records: List[dict], job_id: str) -> dict:
    """Gets a copy of the job of the given job_id

    Args:
        records: the list of records from which to get the job

    Raises:
        KeyError: job of job_id: {job_id} does not exist
    """
    try:
        value = list(filter(lambda x: x["job_id"] == job_id, records))[0]
        return copy.deepcopy(value)
    except IndexError:
        raise KeyError(f"job of job_id: {job_id} does not exist")


def _insert_superuser_app_token(db) -> Dict[str, str]:
    """Gives the superuser a project of their own and an app token for it"""
    project_id = generate_id()
    insert_if_not_exist(
        db,
        Project,
        dict(
            _id=project_id,
            name="superuser-project",
            admin_id=TEST_SUPERUSER_ID,
            user_ids=[TEST_SUPERUSER_ID],
            qpu_seconds=3600,
        ),
    )
    token = "superuser-app-token"
    insert_if_not_exist(
        db,
        AppToken,
        dict(
            title="superuser-token",
            token=token,
            user_id=TEST_SUPERUSER_ID,
            project_id=project_id,
            lifespan_seconds=3600,
        ),
    )
    return {"Authorization": f"Bearer {token}"}


def _prepare_jobs() -> List[dict]:
    """The job fixtures as stored, with timestamps and BCC tokens filled in"""
    jobs = with_current_timestamps(
        _JOBS_LIST, fields=("created_at", "updated_at", "calibration_date")
    )
    return _with_bcc_tokens(jobs)


def _insert_jobs(db, jobs: List[dict]) -> None:
    db.insert_many(Job, [to_record(Job, job) for job in jobs])


def _get_stored_jobs(db, job_filter: Optional[dict] = None) -> List[dict]:
    """Gets the stored jobs as the app shows them, as JSON values"""
    return [job.model_dump(mode="json") for job in db.find(Job, job_filter)]


def _get_job_values(job: dict) -> dict:
    """Gets the JSON values a stored job of these fields would have"""
    return to_record(Job, job).model_dump(mode="json")
