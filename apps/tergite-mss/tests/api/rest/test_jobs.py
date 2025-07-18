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
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import pytest
from beanie import PydanticObjectId
from pytest_lazyfixture import lazy_fixture

from services.auth import Project
from tests._utils.auth import TEST_PROJECT_EXT_ID, get_db_record
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
_JOB_TIMESTAMPED_UPDATES = load_json_fixture("job_timestamped_updates.json")
_JOB_UPDATES = load_json_fixture("job_updates.json")
_JOB_IDS = [item["job_id"] for item in _JOBS_LIST]
_DEVICES = ["loke", "loki", "pingu"]
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
    {"device": "loke"},
    {"device": "pingu"},
    {"device": "pingu", "status": "successful"},
    {"device": "pingu", "status": "pending"},
    {"status": "successful"},
    {"status": "pending"},
    {},
]
_PAGINATE_AND_SEARCH_PARAMS = [
    (skip, limit, sort, search)
    for skip, limit, sort in _SKIP_LIMIT_SORT_PARAMS
    for search in _SEARCH_PARAMS
]


@pytest.mark.parametrize("job_id", _JOB_IDS)
def test_read_job(db, client, job_id: str, no_qpu_app_token_header, freezer):
    """Get to /jobs/{job_id} returns the job for the given job_id"""
    all_jobs = with_current_timestamps(
        _JOBS_LIST, fields=("created_at", "updated_at", "calibration_date")
    )
    insert_in_collection(database=db, collection_name=_COLLECTION, data=all_jobs)

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(f"/jobs/{job_id}", headers=no_qpu_app_token_header)
        got = response.json()
        expected = list(filter(lambda x: x["job_id"] == job_id, all_jobs))[0]

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
):
    """Post to /jobs/ creates a job in the given backend"""
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
        expected_job = {
            "project_id": str(project_id),
            "job_id": new_job_id,
            "user_id": str(current_user_id),
            "device": device,
            "status": "pending",
            "calibration_date": payload["calibration_date"],
            "updated_at": timestamp,
            "created_at": timestamp,
        }
        jobs_after_creation = find_in_collection(
            db,
            collection_name=_COLLECTION,
            fields_to_exclude=_EXCLUDED_FIELDS,
        )

        assert response.status_code == 200
        assert response.json() == {
            "job_id": str(new_job_id),
            "upload_url": f"{expected_bcc_base_url}/jobs",
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


@pytest.mark.parametrize("payload", _CREATE_JOB_PAYLOADS)
def test_create_job_with_auth_disabled(mock_bcc, db, no_auth_client, payload, freezer):
    """Post to /jobs/ creates a job in the given device even when auth is disabled"""
    device = payload["device"]
    expected_bcc_base_url = TEST_BACKENDS_MAP[device]["url"]
    jobs_before_creation = find_in_collection(
        db,
        collection_name=_COLLECTION,
        fields_to_exclude=_EXCLUDED_FIELDS,
    )
    timestamp = get_current_timestamp_str()

    # using context manager to ensure on_startup runs
    with no_auth_client as client:
        response = client.post(f"/jobs/", json=payload)
        json_response = response.json()
        new_job_id = json_response["job_id"]
        expected_job = {
            "job_id": new_job_id,
            "device": device,
            "status": "pending",
            "calibration_date": payload["calibration_date"],
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        jobs_after_creation = find_in_collection(
            db,
            collection_name=_COLLECTION,
            fields_to_exclude=_EXCLUDED_FIELDS,
        )

        assert response.status_code == 200
        assert response.json() == {
            "job_id": str(new_job_id),
            "upload_url": f"{expected_bcc_base_url}/jobs",
        }

        assert jobs_before_creation == []
        assert jobs_after_creation == [expected_job]


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


@pytest.mark.parametrize("raw_payload", _JOB_UPDATES)
def test_update_job(db, client, raw_payload: dict, app_token_header, freezer):
    """PUT to /jobs/{job_id} updates the job with the given object, it ignores job_id"""
    raw_jobs = with_incremental_timestamps(
        _JOBS_LIST, fields=["created_at", "calibration_date"]
    )
    raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])
    insert_in_collection(database=db, collection_name=_COLLECTION, data=raw_jobs)

    ignored_fields = ["unexpected_field", "random_field", "job_id"]
    payload = {**raw_payload, "job_id": f"{uuid.uuid4()}"}
    job_id = raw_payload["job_id"]

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.put(
            f"/jobs/{job_id}",
            json={**payload},
            headers=app_token_header,
        )
        got = response.json()
        expected_job = list(filter(lambda x: x["job_id"] == job_id, raw_jobs))[0]
        actual_update, _ = prune(raw_payload, ignored_fields)
        expected_job.update(
            actual_update,
        )

        job_after_update = find_in_collection(
            db,
            collection_name=_COLLECTION,
            fields_to_exclude=_EXCLUDED_FIELDS,
            _filter={"job_id": job_id},
        )[0]

        assert response.status_code == 200
        assert got == expected_job
        assert job_after_update == expected_job


@pytest.mark.parametrize("raw_payload", _JOB_TIMESTAMPED_UPDATES)
def test_update_job_resource_usage(
    db, client, project_id, raw_payload: dict, app_token_header, freezer
):
    """PUT to /jobs/{job_id} updates the job's resource usage if passed a payload with "timestamps" property"""
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

    # using context manager to ensure on_startup runs
    with client as client:
        # check for idempotence
        for _ in range(3):
            response = client.put(
                f"/jobs/{job_id}",
                json=raw_payload,
                headers=app_token_header,
            )
            assert response.status_code == 200

    project_after_update = get_db_record(
        db, schema=Project, _filter={"ext_id": TEST_PROJECT_EXT_ID}
    )
    expected_resource_usage = _get_resource_usage(raw_payload["timestamps"])
    actual_resource_usage = round(
        project_before_update["qpu_seconds"] - project_after_update["qpu_seconds"], 1
    )

    assert actual_resource_usage == expected_resource_usage


@pytest.mark.parametrize("payload", _JOB_TIMESTAMPED_UPDATES)
def test_update_job_resource_usage_advanced(
    db, client, project_id, payload: dict, app_token_header, freezer
):
    """PUT to /jobs/{job_id} updates the job's resource usage if passed a payload with "timestamps.execution" field"""
    raw_jobs = with_incremental_timestamps(
        _JOBS_LIST, fields=["created_at", "calibration_date"]
    )
    raw_jobs = with_current_timestamps(raw_jobs, fields=["updated_at"])
    job_list = [{**item, "project_id": str(project_id)} for item in raw_jobs]
    insert_in_collection(database=db, collection_name=_COLLECTION, data=job_list)
    job_id = payload["job_id"]

    project_before_update = get_db_record(
        db, schema=Project, _filter={"ext_id": TEST_PROJECT_EXT_ID}
    )

    # using context manager to ensure on_startup runs
    with client as client:
        # check for idempotence
        for _ in range(3):
            response = client.put(
                f"/jobs/{job_id}",
                json=payload,
                headers=app_token_header,
            )
            assert response.status_code == 200

    project_after_update = get_db_record(
        db, schema=Project, _filter={"ext_id": TEST_PROJECT_EXT_ID}
    )
    expected_resource_usage = _get_resource_usage(payload["timestamps"])
    actual_resource_usage = round(
        project_before_update["qpu_seconds"] - project_after_update["qpu_seconds"], 1
    )

    assert actual_resource_usage == expected_resource_usage


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
