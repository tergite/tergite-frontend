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
import json

import httpx
import pytest

from libs.storage import generate_id
from services.calibration import DeviceCalibration
from services.devices import Device
from services.jobs import Job
from tests._utils.auth import (
    TEST_NO_QPU_PROJECT_ID,
    TEST_PROJECT_ID,
    TEST_SUPERUSER_ID,
    TEST_USER_ID,
)
from tests._utils.bcc import create_bcc_client_jwt_token, encrypt_jwt_token
from tests._utils.fixtures import load_json_fixture
from tests._utils.storage import to_record

_BCC_URL = "http://testclient"
_BELL = """OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c = measure q;
"""
_SUBMISSION = {
    "project_id": TEST_PROJECT_ID,
    "device": "Loke",
    "shots": 1024,
    "circuits": [{"name": "bell", "qasm": _BELL}],
}
_LOKE = next(v for v in load_json_fixture("device_list.json") if v["name"] == "Loke")
_LOKE_CALIBRATION = next(
    v for v in load_json_fixture("calibrations.json") if v["name"] == "Loke"
)


@pytest.fixture
def loke(db):
    """Loke and its calibration, stored"""
    db.insert(Device, to_record(Device, {**_LOKE, "id": generate_id()}))
    db.insert(DeviceCalibration, to_record(DeviceCalibration, _LOKE_CALIBRATION))
    yield _LOKE


@pytest.fixture
def uploads(mock_bcc):
    """The job files the backend is sent, as it takes them"""
    route = mock_bcc.post(f"{_BCC_URL}/jobs").mock(
        return_value=httpx.Response(200, json={"message": "job received"})
    )
    yield route


def test_submitting_a_job_uploads_its_file_and_keeps_its_source(
    db, client, loke, uploads, user_jwt_cookie
):
    with client as client:
        response = client.post("/me/jobs/", json=_SUBMISSION, cookies=user_jwt_cookie)

    job = response.json()
    stored = db.get(Job, job["job_id"])
    upload = uploads.calls.last.request
    assert response.status_code == 201
    assert job["status"] == "pending"
    assert job["access_token"] is None
    assert (stored.project_id, stored.user_id) == (TEST_PROJECT_ID, TEST_USER_ID)
    assert stored.calibration_date == _LOKE_CALIBRATION["last_calibrated"]
    assert stored.source.model_dump() == {
        "shots": 1024,
        "meas_level": 2,
        "meas_return": "single",
        "circuits": [{"name": "bell", "qasm": _BELL}],
    }
    assert upload.headers["authorization"].startswith("Bearer ")
    assert _read_job_file(upload) == {
        "job_id": job["job_id"],
        "params": {
            "circuits": [{"name": "bell", "qasm": _BELL, "num_clbits": 2}],
            "shots": 1024,
            "meas_level": 2,
            "meas_return": "single",
        },
    }


@pytest.mark.parametrize(
    "qasm, message, line, column",
    [
        (
            "OPENQASM 3.0;\nqubit[2] q;\nh q[0]\ncx q[0], q[1];\n",
            "missing ';' at 'cx'",
            4,
            1,
        ),
        (
            "OPENQASM 3.0;\nqubit[9] q;\nbit[1] c;\nc[0] = measure q[0];\n",
            "the circuit uses 9 qubits, but Loke has 8",
            None,
            None,
        ),
        (
            'OPENQASM 3.0;\ndefcalgrammar "openpulse";\nbit[1] c;\n'
            "cal { c[0] = capture_v1(q12_readout, 2us); }\n",
            "project test-project may not send pulse-level programs; an admin can allow it",
            None,
            None,
        ),
    ],
    ids=["syntax", "too-many-qubits", "pulse-without-leave"],
)
def test_a_circuit_the_device_cannot_run_is_refused_before_a_job_is_made(
    db, client, loke, uploads, user_jwt_cookie, qasm, message, line, column
):
    second = {"name": "second", "qasm": qasm}
    payload = {**_SUBMISSION, "circuits": [*_SUBMISSION["circuits"], second]}

    with client as client:
        response = client.post("/me/jobs/", json=payload, cookies=user_jwt_cookie)

    assert response.status_code == 422
    assert response.json()["detail"] == [
        {
            "type": "invalid_circuit",
            "loc": ["body", "circuits", 1, "qasm"],
            "msg": message,
            "input": None,
            "ctx": {"line": line, "column": column},
        }
    ]
    assert db.find(Job, {}) == []
    assert not uploads.called


@pytest.mark.parametrize(
    "project_id, status_code",
    [(TEST_NO_QPU_PROJECT_ID, 403), (generate_id(), 401)],
    ids=["no-qpu-left", "not-a-member"],
)
def test_a_job_needs_a_project_of_the_users_with_qpu_left(
    db, client, loke, uploads, user_jwt_cookie, project_id, status_code
):
    payload = {**_SUBMISSION, "project_id": project_id}

    with client as client:
        response = client.post("/me/jobs/", json=payload, cookies=user_jwt_cookie)

    assert response.status_code == status_code
    assert db.find(Job, {}) == []


def test_a_job_file_the_backend_refuses_fails_the_job_with_its_reason(
    db, client, loke, mock_bcc, user_jwt_cookie
):
    reason = "the device takes no pulse-level jobs"
    mock_bcc.post(f"{_BCC_URL}/jobs").mock(
        return_value=httpx.Response(400, json={"detail": reason})
    )

    with client as client:
        response = client.post("/me/jobs/", json=_SUBMISSION, cookies=user_jwt_cookie)

    (stored,) = db.find(Job, {})
    assert response.status_code == 400
    assert response.json()["detail"] == reason
    assert (stored.status, stored.failure_reason) == ("failed", reason)


def test_reading_a_job_shows_its_source_but_not_its_token(
    db, client, user_jwt_cookie, admin_jwt_cookie
):
    job = _insert_job(db, user_id=TEST_SUPERUSER_ID)

    with client as client:
        own = client.get(f"/me/jobs/{job.job_id}", cookies=admin_jwt_cookie)
        others = client.get(f"/me/jobs/{job.job_id}", cookies=user_jwt_cookie)

    assert own.status_code == 200
    assert own.json()["source"]["circuits"] == [{"name": "bell", "qasm": _BELL}]
    assert own.json()["access_token"] is None
    assert others.status_code == 404


def test_a_jobs_logfile_is_fetched_from_the_backend_with_its_token(
    db, client, mock_bcc, user_jwt_cookie
):
    download_url = f"{_BCC_URL}/logfiles/some-job"
    job = _insert_job(db, user_id=TEST_USER_ID, download_url=download_url)
    logfile = mock_bcc.get(download_url).mock(
        return_value=httpx.Response(200, content=b"\x89HDF\r\n")
    )

    with client as client:
        response = client.get(f"/me/jobs/{job.job_id}/logfile", cookies=user_jwt_cookie)

    token = logfile.calls.last.request.headers["authorization"]
    assert response.status_code == 200
    assert response.content == b"\x89HDF\r\n"
    assert response.headers["content-type"] == "application/x-hdf5"
    assert token == f"Bearer {job.plain_token}"


def test_a_job_without_a_logfile_has_none_to_fetch(db, client, user_jwt_cookie):
    job = _insert_job(db, user_id=TEST_USER_ID)

    with client as client:
        response = client.get(f"/me/jobs/{job.job_id}/logfile", cookies=user_jwt_cookie)

    assert response.status_code == 404


class _StoredJob(Job):
    """A stored job, with the plain token its encrypted one hides"""

    plain_token: str = ""


def _insert_job(db, user_id: str, download_url=None) -> _StoredJob:
    """Stores a dashboard job of the user's on Loke, with a backend token"""
    job = Job(
        device="Loke",
        calibration_date=_LOKE_CALIBRATION["last_calibrated"],
        project_id=TEST_PROJECT_ID,
        user_id=user_id,
        download_url=download_url,
        source={"shots": 1024, "circuits": [{"name": "bell", "qasm": _BELL}]},
    )
    plain_token = create_bcc_client_jwt_token(user_id=user_id, job_id=job.job_id)
    job.access_token = encrypt_jwt_token(plain_token)
    db.insert(Job, job)
    return _StoredJob(**job.model_dump(), plain_token=plain_token)


def _read_job_file(request: httpx.Request) -> dict:
    """The JSON job file in a multipart upload"""
    body = request.content.split(b"\r\n\r\n", 1)[1]
    return json.loads(body.rsplit(b"\r\n--", 1)[0])
