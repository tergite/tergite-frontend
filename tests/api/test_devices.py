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
"""Integration tests for the devices router"""
import copy
import uuid
from typing import Any, Dict, List, Optional

import pytest
from fastapi.websockets import WebSocketDisconnect

from libs.storage import generate_id
from services.devices import Device
from tests._utils.bcc import create_bcc_headers
from tests._utils.date_time import is_not_older_than
from tests._utils.fixtures import load_json_fixture
from tests._utils.records import (
    filter_by_equality,
    get_record,
    order_by_many,
    pop_field,
    with_incremental_timestamps,
)
from tests._utils.storage import to_record

_DEVICE_LIST = load_json_fixture("device_list.json")
_SKIP_LIMIT_SORT_PARAMS = [
    (0, 1, ["-version", "updated_at"]),
    (2, 4, None),
    (1, 3, ["version", "created_at"]),
    (None, 10, None),
    (2, None, ["created_at"]),
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
# an offline real device and an online simulator
_SAMPLE_DEVICES = [_DEVICE_LIST[0], _DEVICE_LIST[1]]


@pytest.mark.parametrize("skip, limit, sort, search", _PAGINATE_AND_SEARCH_PARAMS)
def test_find_devices(
    db,
    client,
    skip: Optional[int],
    limit: Optional[int],
    sort: Optional[List[str]],
    search: dict,
    freezer,
):
    """Get to /devices/?version=...&name=... can search for the devices that fulfill the given filters"""
    raw_devices = with_incremental_timestamps(
        _DEVICE_LIST, fields=("created_at", "updated_at")
    )
    raw_devices = [{**item, "id": generate_id()} for item in raw_devices]
    db.insert_many(Device, [to_record(Device, item) for item in raw_devices])

    query_string = "?"
    slice_end = len(raw_devices)
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
        response = client.get(f"/devices/{query_string}")
        got = response.json()

        filtered_data = filter_by_equality(raw_devices, filters=search)
        sorted_data = order_by_many(filtered_data, fields=sort_fields)
        expected = {
            "skip": slice_start,
            "limit": limit,
            "data": sorted_data[slice_start:slice_end],
        }

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("name", [v["name"] for v in _SAMPLE_DEVICES])
def test_read_one_device(db, client, name: str, user_jwt_cookie):
    """GET to /devices/{name} returns the device of the given name"""
    devices = [{**item, "id": generate_id()} for item in _DEVICE_LIST]
    db.insert_many(Device, [to_record(Device, item) for item in devices])

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(f"/devices/{name}", cookies=user_jwt_cookie)
        got: dict = response.json()
        got.pop("id")
        expected = get_record(_DEVICE_LIST, _filter={"name": name})

        assert response.status_code == 200
        assert expected == got


@pytest.mark.parametrize("payload", _SAMPLE_DEVICES)
def test_create_device(db, client, payload: Dict[str, Any]):
    """DeviceEvent with name 'initialized' to /devices/ws/{name} creates a new device if it does not exist"""
    original_data_in_db = _get_stored_devices(db)
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
                    "name": "initialized",
                    "data": payload,
                }
            )
            json_response = client.receive_json()
            final_data_in_db = _get_stored_devices(db)

            assert json_response["status"] == "success"
            json_response["data"].pop("id")
            assert json_response["data"] == final_data_in_db[0]

            created_at_timestamps = pop_field(final_data_in_db, "created_at")
            updated_at_timestamps = pop_field(final_data_in_db, "updated_at")

            assert original_data_in_db == []
            assert final_data_in_db == [payload]
            assert all(
                [is_not_older_than(x, seconds=30) for x in created_at_timestamps]
            )
            assert all(
                [is_not_older_than(x, seconds=30) for x in updated_at_timestamps]
            )


def test_a_replayed_nonce_is_refused(client):
    """A second websocket with the same signed x-request-id is refused as a replay"""
    name = _DEVICE_LIST[0]["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers(name)

    with client as client:
        with client.websocket_connect(url, headers=headers):
            pass

        with pytest.raises(WebSocketDisconnect) as exp:
            with client.websocket_connect(url, headers=headers):
                pass

    assert exp.value.code == 1008


@pytest.mark.parametrize("payload", _SAMPLE_DEVICES[:1])
def test_create_device_wrong_cert(db, client, payload: Dict[str, Any], user_jwt_cookie):
    """Only clients with the certificate known to MSS can push to /devices/ws/{name}"""
    original_data_in_db = _get_stored_devices(db)

    name = payload["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers("WrongCert")

    with pytest.raises(WebSocketDisconnect) as exp:
        with client as client:
            with client.websocket_connect(url, headers=headers):
                pass

    final_data_in_db = _get_stored_devices(db)

    assert exp.value.code == 1008
    assert exp.value.reason == "unauthorized"
    assert original_data_in_db == []
    assert final_data_in_db == []


@pytest.mark.parametrize("payload", _SAMPLE_DEVICES[:1])
def test_create_device_wrong_payload(
    db, client, payload: Dict[str, Any], user_jwt_cookie
):
    """BCC devices can only push their own device data to /devices/ws/{name} and not those of others"""
    original_data_in_db = _get_stored_devices(db)

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
                    "name": "initialized",
                    "data": payload,
                }
            )
            response = client.receive_json()
            final_data_in_db = _get_stored_devices(db)

            assert response == {
                "id": event_id,
                "status": "error",
                "detail": f"forbidden: editing '{payload['name']}' is not allowed",
            }

            assert original_data_in_db == []
            assert final_data_in_db == []


@pytest.mark.parametrize("payload", _SAMPLE_DEVICES[:1])
def test_create_device_wrong_url(db, client, payload: Dict[str, Any], user_jwt_cookie):
    """BCC devices can only push to their own urls /devices/ws/{name}/ and not those of others"""
    original_data_in_db = _get_stored_devices(db)

    name = payload["name"]
    url = f"/devices/ws/{name}extra"
    headers = create_bcc_headers(name)

    with pytest.raises(WebSocketDisconnect) as exp:
        with client as client:
            with client.websocket_connect(url, headers=headers):
                pass

    final_data_in_db = _get_stored_devices(db)

    assert exp.value.code == 1008
    assert exp.value.reason == "forbidden"
    assert original_data_in_db == []
    assert final_data_in_db == []


@pytest.mark.parametrize("backend_dict", _SAMPLE_DEVICES)
def test_update_pre_existing_device(
    db, client, backend_dict: Dict[str, Any], system_app_token_header
):
    """Pushing 'initialized'-DeviceEvent to /devices/ws/{name} a pre-existing device updates it"""
    db.insert(Device, to_record(Device, {**backend_dict, "id": generate_id()}))
    original_data_in_db = _get_stored_devices(db)
    name = backend_dict["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers(name)
    payload = {
        **backend_dict,
        "number_of_couplers": 100,
        "number_of_qubits": 80,
    }

    # using context manager to ensure on_startup runs
    with client as client:
        with client.websocket_connect(url, headers=headers) as client:
            event_id = str(uuid.uuid4())
            client.send_json(
                {
                    "id": event_id,
                    "name": "initialized",
                    "data": payload,
                }
            )
            json_response = client.receive_json()
            final_data_in_db = _get_stored_devices(db)

            assert json_response["status"] == "success"
            json_response["data"].pop("id")
            assert json_response["data"] == final_data_in_db[0]

            updated_at_timestamps = pop_field(final_data_in_db, "updated_at")
            expected = {
                **original_data_in_db[0],
                **payload,
            }

            assert original_data_in_db == [backend_dict]
            assert final_data_in_db[0] == expected
            assert all(
                [is_not_older_than(x, seconds=30) for x in updated_at_timestamps]
            )


def _get_stored_devices(db) -> List[Dict[str, Any]]:
    """Gets the stored devices as the app shows them, without their ids"""
    return [
        device.model_dump(mode="json", exclude={"id"}, exclude_none=True)
        for device in db.find(Device)
    ]
