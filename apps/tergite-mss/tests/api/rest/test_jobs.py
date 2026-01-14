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
from beanie import PydanticObjectId
from pytest_lazyfixture import lazy_fixture
from pytest_mock import MockerFixture

from services.auth import Project
from tests._utils.auth import TEST_PROJECT_EXT_ID, TEST_USER_ID, get_db_record
from tests._utils.bcc import create_bcc_headers
from tests._utils.date_time import (
    get_current_timestamp_str,
)
from tests._utils.env import TEST_BACKENDS_MAP
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import find_in_collection, insert_in_collection
from tests._utils.records import (
    filter_by_equality,
    order_by_many,
    prune,
    with_current_timestamps,
    with_incremental_timestamps,
)

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
_COLLECTION = "jobs"
_EXCLUDED_FIELDS = ["_id"]
_UNAVAILABLE_BCC_FIXTURE = [
    ({"device": device, "calibration_date": "2024-05-23T09:12:00.733Z"}, client)
    for device in _DEVICES
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
_PAGINATE_AND_SEARCH_PARAMS = [
    (skip, limit, sort, search)
    for skip, limit, sort in _SKIP_LIMIT_SORT_PARAMS
    for search in _SEARCH_PARAMS
]
_DEVICES_AND_JOB_UPDATES = [
    (device, job_update) for device in _DEVICES[:2] for job_update in _JOB_UPDATES
]
_DEVICES_AND_JOB_TIMESTAMPED_UPDATES = [
    (device, job_update)
    for device in _DEVICES[:2]
    for job_update in _JOB_TIMESTAMPED_UPDATES
]


@pytest.mark.parametrize("job_id", _JOB_IDS)
def test_read_job(db, client, job_id: str, no_qpu_app_token_header, freezer):
    """Get to /jobs/{job_id} returns the job for the given job_id"""
    all_jobs = with_current_timestamps(
        _JOBS_LIST, fields=("created_at", "updated_at", "calibration_date")
    )
    all_jobs = _with_bcc_tokens(all_jobs)
    expected = _get_job(all_jobs, job_id=job_id)
    if job_id in _JOB_BCC_TOKEN_MAP:
        expected["access_token"] = _JOB_BCC_TOKEN_MAP[job_id]["plain"]

    insert_in_collection(database=db, collection_name=_COLLECTION, data=all_jobs)

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(f"/jobs/{job_id}", headers=no_qpu_app_token_header)
        got = response.json()

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("payload", _CREATE_JOB_PAYLOADS)
def test_create_job(
    mock_bcc,
    db,
    client,
    payload,
    project_id: PydanticObjectId,
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
    expected_bcc_base_url = TEST_BACKENDS_MAP[device]["url"]
    jobs_before_creation = find_in_collection(
        db,
        collection_name=_COLLECTION,
        fields_to_exclude=_EXCLUDED_FIELDS,
    )
    timestamp = get_current_timestamp_str()

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post(f"/jobs/", json=payload, headers=app_token_header)
        json_response = response.json()
        new_job_id = json_response["job_id"]
        jobs_after_creation = find_in_collection(
            db,
            collection_name=_COLLECTION,
            fields_to_exclude=_EXCLUDED_FIELDS,
        )
        plain_token = jwt_encode_spy.spy_return
        encrypted_token_bytes = base64_b64encode_spy.spy_return
        encrypted_token = encrypted_token_bytes.decode()

        mocker.stop(jwt_encode_spy)
        mocker.stop(base64_b64encode_spy)

        expected_job = {
            "project_id": str(project_id),
            "job_id": new_job_id,
            "user_id": str(current_user_id),
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
        assert jobs_after_creation == [expected_job]


@pytest.mark.parametrize("payload, bcc", _UNAVAILABLE_BCC_FIXTURE)
def test_create_job_without_bcc(db, client, payload, app_token_header, bcc):
    """Post to /jobs/ error out if BCC is not available"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.post(f"/jobs/", json=payload, headers=app_token_header)
        jobs_after_creation = find_in_collection(
            db,
            collection_name=_COLLECTION,
            fields_to_exclude=_EXCLUDED_FIELDS,
        )

        assert response.status_code == 503
        assert response.json() == {"detail": "device is currently unavailable"}
        # no job created
        assert jobs_after_creation == []


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
    insert_in_collection(database=db, collection_name=_COLLECTION, data=raw_jobs)

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

    insert_in_collection(database=db, collection_name=_COLLECTION, data=raw_jobs)

    ignored_fields = ["unexpected_field", "random_field"]

    url = f"/devices/ws/{device}"
    headers = create_bcc_headers(device)

    # using context manager to ensure on_startup runs
    with client.websocket_connect(url, headers=headers) as client:
        client.send_json(
            {
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

        job_after_update = find_in_collection(
            db,
            collection_name=_COLLECTION,
            fields_to_exclude=_EXCLUDED_FIELDS,
            _filter={"job_id": job_id},
        )[0]

        assert response["status"] == "success"
        assert got == expected_response
        assert job_after_update == expected_job


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
    job_id = raw_payload["job_id"]

    insert_in_collection(database=db, collection_name=_COLLECTION, data=job_list)

    project_before_update = get_db_record(
        db, schema=Project, _filter={"ext_id": TEST_PROJECT_EXT_ID}
    )

    url = f"/devices/ws/{device}"
    headers = create_bcc_headers(device)

    # using context manager to ensure on_startup runs
    with client.websocket_connect(url, headers=headers) as client:
        client.send_json(
            {
                "name": "job_updated",
                "data": raw_payload,
            }
        )
        response = client.receive_json()
        assert response["status"] == "success"

    project_after_update = get_db_record(
        db, schema=Project, _filter={"ext_id": TEST_PROJECT_EXT_ID}
    )
    expected_resource_usage = _get_resource_usage(raw_payload["timestamps"])
    actual_resource_usage = round(
        project_before_update["qpu_seconds"] - project_after_update["qpu_seconds"], 1
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
    insert_in_collection(database=db, collection_name=_COLLECTION, data=job_list)

    project_before_update = get_db_record(
        db, schema=Project, _filter={"ext_id": TEST_PROJECT_EXT_ID}
    )

    url = f"/devices/ws/{device}"
    headers = create_bcc_headers(device)

    # using context manager to ensure on_startup runs
    with client.websocket_connect(url, headers=headers) as client:
        client.send_json(
            {
                "name": "job_updated",
                "data": payload,
            }
        )
        response = client.receive_json()
        assert response["status"] == "success"

    project_after_update = get_db_record(
        db, schema=Project, _filter={"ext_id": TEST_PROJECT_EXT_ID}
    )
    expected_resource_usage = _get_resource_usage(payload["timestamps"])
    actual_resource_usage = round(
        project_before_update["qpu_seconds"] - project_after_update["qpu_seconds"], 1
    )

    assert actual_resource_usage == expected_resource_usage


@pytest.mark.parametrize("job", _JOBS_LIST[:4])
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

        insert_in_collection(database=db, collection_name=_COLLECTION, data=raw_jobs)

        response = client.post(
            f"/jobs/{job_id}/cancel",
            json={"reason": cancellation_reason},
            cookies=user_jwt_cookie,
        )
        got = response.json()
        job_in_db = find_in_collection(
            db,
            collection_name=_COLLECTION,
            fields_to_exclude=_EXCLUDED_FIELDS,
            _filter={"job_id": job_id},
        )[0]

        assert response.status_code == 200
        assert got == {
            "status": "success",
            "detail": f"Job of id {job_id} cancelled",
        }

        assert job_in_db == {
            **job_info,
            "status": "cancelled",
            "cancellation_reason": cancellation_reason,
        }


@pytest.mark.parametrize("job", _JOBS_LIST[:4])
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

        insert_in_collection(database=db, collection_name=_COLLECTION, data=raw_jobs)

        payload = {"reason": cancellation_reason}
        url = f"/jobs/{job_id}/cancel"

        response = client.post(url, json=payload)
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

        invalid_headers = {"Auhtorization": "Bearer some-wrong-token"}
        response = client.post(url, headers=invalid_headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.parametrize("idx", range(4))
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

        insert_in_collection(database=db, collection_name=_COLLECTION, data=raw_jobs)

        response = client.delete(f"/jobs/{job_id}", cookies=user_jwt_cookie)
        got = response.json()
        jobs_in_db = find_in_collection(
            db,
            collection_name=_COLLECTION,
            fields_to_exclude=_EXCLUDED_FIELDS,
            _filter={},
        )
        expected_jobs = [item for item in raw_jobs if item["job_id"] != job_id]

        assert response.status_code == 200
        assert got == {
            "status": "success",
            "detail": f"Job of id {job_id} deleted",
        }

        assert jobs_in_db == expected_jobs


@pytest.mark.parametrize("idx", range(4))
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

        insert_in_collection(database=db, collection_name=_COLLECTION, data=raw_jobs)

        response = client.delete(f"/jobs/{job_id}")
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

        invalid_headers = {"Auhtorization": "Bearer some-wrong-token"}
        response = client.delete(f"/jobs/{job_id}", headers=invalid_headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


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
