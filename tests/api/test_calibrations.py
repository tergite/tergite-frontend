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
"""Tests for calibrations"""
import copy
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest
from fastapi.websockets import WebSocketDisconnect

from libs.storage import generate_id
from services.calibration import DeviceCalibration, DeviceCalibrationLog
from tests._utils.bcc import create_bcc_headers
from tests._utils.date_time import get_current_timestamp_str, get_timestamp_str
from tests._utils.fixtures import load_json_fixture
from tests._utils.records import (
    distinct_on,
    filter_by_equality,
    order_by,
    order_by_many,
    with_current_timestamps,
    with_incremental_timestamps,
)
from tests._utils.storage import to_record

_CALIBRATIONS_LIST = load_json_fixture("calibrations.json")
_LATEST_CALIBRATIONS = distinct_on(
    order_by(_CALIBRATIONS_LIST, field="last_calibrated", is_descending=True),
    field="name",
)
_DEVICE_NAMES = [item["name"] for item in _LATEST_CALIBRATIONS]
_SKIP_LIMIT_SORT_PARAMS = [
    (0, 1, ["-version", "last_calibrated"]),
    (2, 4, None),
    (1, 3, ["version"]),
    (None, 10, None),
    (2, None, ["last_calibrated"]),
]
_SEARCH_PARAMS = [
    {"version": "2024.04.1"},
    {"name": "Loke"},
    {"version": "2023.06.0"},
    {"version": "2023.06.0", "name": "Loke"},
    {"version": "2023.06.0", "name": "Thor"},
    {},
]
# paging and searching are independent, so each is tested without the other
_PAGINATE_AND_SEARCH_PARAMS = [
    *((skip, limit, sort, {}) for skip, limit, sort in _SKIP_LIMIT_SORT_PARAMS),
    *((None, None, None, search) for search in _SEARCH_PARAMS if search),
]


@pytest.mark.parametrize("skip, limit, sort, search", _PAGINATE_AND_SEARCH_PARAMS)
def test_find_calibrations(
    db,
    client,
    skip: Optional[int],
    limit: Optional[int],
    sort: Optional[List[str]],
    search: dict,
    freezer,
):
    """Get to /calibrations/?version=...&name=... can search for the calibrations that fulfill the given filters"""
    raw_calibrations = with_incremental_timestamps(
        _LATEST_CALIBRATIONS, fields=("last_calibrated", "updated_at")
    )
    raw_calibrations = [{**item, "id": generate_id()} for item in raw_calibrations]
    db.insert_many(
        DeviceCalibration,
        [to_record(DeviceCalibration, item) for item in raw_calibrations],
    )

    query_string = "?"
    slice_end = len(raw_calibrations)
    slice_start = 0
    sort_fields = [
        "-last_calibrated",
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
        response = client.get(f"/calibrations/{query_string}")
        got = response.json()

        filtered_data = filter_by_equality(raw_calibrations, filters=search)
        sorted_data = order_by_many(filtered_data, fields=sort_fields)
        expected = {
            "skip": slice_start,
            "limit": limit,
            "data": sorted_data[slice_start:slice_end],
        }

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("name", _DEVICE_NAMES)
def test_read_calibration(name: str, db, client, freezer):
    """Get `/calibrations/{name}` reads the latest calibration of the given device"""
    raw_calibrations = with_incremental_timestamps(
        _LATEST_CALIBRATIONS, fields=("last_calibrated", "updated_at")
    )
    raw_calibrations = [{**item, "id": generate_id()} for item in raw_calibrations]
    db.insert_many(
        DeviceCalibration,
        [to_record(DeviceCalibration, item) for item in raw_calibrations],
    )

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(f"/calibrations/{name}")
        got = response.json()
        expected = filter_by_equality(raw_calibrations, {"name": name})[0]

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("payload", _CALIBRATIONS_LIST)
def test_create(db, client, payload, freezer):
    """Push to /devices/ws/{name} event with name 'recalibrated' creates new calibration and returns it"""
    name = payload["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers(name)

    # using context manager to ensure on_startup runs
    with client as client:
        with client.websocket_connect(url, headers=headers) as client:
            event_id = str(uuid.uuid4())
            client.send_json(
                {
                    "id": event_id,
                    "name": "recalibrated",
                    "data": payload,
                }
            )
            json_response = client.receive_json()

            assert json_response == {
                "id": event_id,
                "status": "success",
                "data": {
                    **payload,
                    "updated_at": get_current_timestamp_str(),
                    "id": json_response["data"]["id"],
                },
            }


@pytest.mark.parametrize("raw_payload", _CALIBRATIONS_LIST)
def test_upsert(db, client, raw_payload, freezer):
    """push 'recalibrated' event to /devices/ws/{name} for an existing calibration updates it"""
    raw_calibrations = with_current_timestamps(
        [raw_payload], fields=("updated_at", "last_calibrated")
    )
    db.insert_many(
        DeviceCalibration,
        [to_record(DeviceCalibration, item) for item in raw_calibrations],
    )

    now = get_current_timestamp_str()
    future_timestamp = get_timestamp_str(
        datetime.now(timezone.utc) + timedelta(hours=2)
    )
    payload = {
        **raw_payload,
        "last_calibrated": future_timestamp,
        "resonators": None,
        "discriminators": None,
    }
    name = payload["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers(name)

    # using context manager to ensure on_startup runs
    with client as client:
        with client.websocket_connect(url, headers=headers) as client:
            event_id = str(uuid.uuid4())
            client.send_json(
                {
                    "id": event_id,
                    "name": "recalibrated",
                    "data": payload,
                }
            )
            json_response = client.receive_json()
            record_id = json_response["data"]["id"]

            assert json_response == {
                "id": event_id,
                "status": "success",
                "data": {**payload, "updated_at": now, "id": record_id},
            }

            new_calibration = to_record(
                DeviceCalibration, {**payload, "updated_at": now, "id": record_id}
            )
            assert db.find(DeviceCalibration) == [new_calibration]


@pytest.mark.parametrize("raw_payload", _CALIBRATIONS_LIST)
def test_create_log(db, client, system_app_token_header, raw_payload, freezer):
    """Pushing 'recalibrated' event to /devices/ws/{name} adds the calibration to calibrations_logs if not exist"""
    raw_calibrations = with_current_timestamps(
        _LATEST_CALIBRATIONS, fields=("updated_at",)
    )
    # insert only some of the calibrations in collection to show upsert is done
    original_logs_in_db = raw_calibrations[:2]
    db.insert_many(
        DeviceCalibrationLog,
        [to_record(DeviceCalibrationLog, item) for item in original_logs_in_db],
    )

    future_timestamp = get_timestamp_str(
        datetime.now(timezone.utc) + timedelta(hours=2)
    )
    payload = {**raw_payload, "last_calibrated": future_timestamp}
    name = payload["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers(name)

    # using context manager to ensure on_startup runs
    with client as client:
        with client.websocket_connect(url, headers=headers) as client:
            event_id = str(uuid.uuid4())
            client.send_json(
                {
                    "id": event_id,
                    "name": "recalibrated",
                    "data": payload,
                }
            )
            json_response = client.receive_json()
            got = _get_stored_values(db, DeviceCalibrationLog)
            expected = [
                _get_values(DeviceCalibrationLog, item)
                for item in [*original_logs_in_db, payload]
            ]

            assert json_response["status"] == "success"
            assert order_by(got, "name") == order_by(expected, "name")


@pytest.mark.parametrize("payload", _CALIBRATIONS_LIST[:1])
def test_create_wrong_cert(db, client, payload: Dict[str, Any], user_jwt_cookie):
    """Only clients with the certificate known to MSS can push to /ws/devices/"""
    original_data_in_db = _get_stored_values(db, DeviceCalibration)

    name = payload["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers("WrongCert")

    with pytest.raises(WebSocketDisconnect) as exp:
        with client as client:
            with client.websocket_connect(url, headers=headers):
                pass

    final_data_in_db = _get_stored_values(db, DeviceCalibration)

    assert exp.value.code == 1008
    assert exp.value.reason == "unauthorized"
    assert original_data_in_db == []
    assert final_data_in_db == []


@pytest.mark.parametrize("payload", _CALIBRATIONS_LIST[:1])
def test_create_wrong_payload(db, client, payload: Dict[str, Any], user_jwt_cookie):
    """BCC devices can only push their own calibration data to /ws/devices/ and not those of others"""
    original_data_in_db = _get_stored_values(db, DeviceCalibration)

    # just to ensure mutations occur on copies and not on the original object
    payload = copy.deepcopy(payload)
    name = payload["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers(name)

    # using context manager to ensure on_startup runs
    with client as client:
        with client.websocket_connect(url, headers=headers) as client:
            payload["name"] = f"{payload['name']}extra"
            event_id = str(uuid.uuid4())
            client.send_json(
                {
                    "id": event_id,
                    "name": "recalibrated",
                    "data": payload,
                }
            )
            response = client.receive_json()
            final_data_in_db = _get_stored_values(db, DeviceCalibration)

            assert response == {
                "id": event_id,
                "status": "error",
                "detail": f"forbidden: editing '{payload['name']}' is not allowed",
            }

            assert original_data_in_db == []
            assert final_data_in_db == []


@pytest.mark.parametrize(
    "frame",
    [
        {"name": "q00_flux", "kind": "flux", "qubits": [0], "frequency": 4.6e9},
        {"name": "q00_drive", "kind": "drive", "qubits": [0]},
    ],
    ids=["unknown-kind", "no-frequency"],
)
def test_create_with_a_malformed_frame_is_refused(db, client, frame):
    payload = {**_CALIBRATIONS_LIST[0], "frames": [frame]}
    name = payload["name"]
    headers = create_bcc_headers(name)

    with client as client:
        with client.websocket_connect(f"/devices/ws/{name}", headers=headers) as ws:
            ws.send_json({"id": "1", "name": "recalibrated", "data": payload})
            response = ws.receive_json()

    assert response["status"] == "error"
    assert response["detail"].startswith(
        "invalid data: 1 validation error for DeviceEvent"
    )
    assert _get_stored_values(db, DeviceCalibration) == []


@pytest.mark.parametrize("payload", _CALIBRATIONS_LIST[:1])
def test_create_wrong_url(db, client, payload: Dict[str, Any], user_jwt_cookie):
    """BCC devices can only push to their own urls /ws/devices/{name}/ and not those of others"""
    original_data_in_db = _get_stored_values(db, DeviceCalibration)

    name = payload["name"]
    url = f"/devices/ws/{name}extra"
    headers = create_bcc_headers(name)

    with pytest.raises(WebSocketDisconnect) as exp:
        with client as client:
            with client.websocket_connect(url, headers=headers):
                pass

    final_data_in_db = _get_stored_values(db, DeviceCalibration)

    assert exp.value.code == 1008
    assert exp.value.reason == "forbidden"
    assert original_data_in_db == []
    assert final_data_in_db == []


def _get_stored_values(db, schema) -> List[Dict[str, Any]]:
    """Gets the stored records of the schema as JSON values, without their ids"""
    return [
        record.model_dump(mode="json", exclude={"id"}) for record in db.find(schema)
    ]


def _get_values(schema, document: Dict[str, Any]) -> Dict[str, Any]:
    """Gets a document as JSON values of a record of the schema, without its id"""
    record = to_record(schema, {**document, "id": generate_id()})
    return record.model_dump(mode="json", exclude={"id"})
