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
from typing import Any, Dict, List, Optional

import pytest
from fastapi.websockets import WebSocketDisconnect

from tests._utils.bcc import create_bcc_headers
from tests._utils.date_time import is_not_older_than
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import find_in_collection, insert_in_collection
from tests._utils.records import (
    filter_by_equality,
    get_record,
    order_by_many,
    pop_field,
    with_incremental_timestamps,
)
from tests.api.rest.test_calibrations import _attach_str_ids

_DEVICES_COLLECTION = "devices"
_EXCLUDED_FIELDS = ["_id"]

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
_PAGINATE_AND_SEARCH_PARAMS = [
    (skip, limit, sort, search)
    for skip, limit, sort in _SKIP_LIMIT_SORT_PARAMS
    for search in _SEARCH_PARAMS
]


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
    inserted_ids = insert_in_collection(
        database=db, collection_name=_DEVICES_COLLECTION, data=raw_devices
    )
    raw_devices = _attach_str_ids(raw_devices, ids=inserted_ids, id_field="id")

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


@pytest.mark.parametrize("name", [v["name"] for v in _DEVICE_LIST])
def test_read_one_device(db, client, name: str, user_jwt_cookie):
    """GET to /devices/{name} returns the device of the given name"""
    insert_in_collection(
        database=db, collection_name=_DEVICES_COLLECTION, data=_DEVICE_LIST
    )

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(f"/devices/{name}", cookies=user_jwt_cookie)
        got: dict = response.json()
        got.pop("id")
        expected = get_record(_DEVICE_LIST, _filter={"name": name})

        assert response.status_code == 200
        assert expected == got


@pytest.mark.parametrize("payload", _DEVICE_LIST)
def test_create_device(db, client, payload: Dict[str, Any]):
    """DeviceStatusMessage with status 'initialized' to /devices/ws/{name} creates a new device if it does not exist"""
    original_data_in_db = find_in_collection(
        db, collection_name=_DEVICES_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
    )
    name = payload["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers(name)

    # using context manager to ensure on_startup runs
    with client.websocket_connect(url, headers=headers) as client:
        client.send_json(
            {
                "status": "initialized",
                "data": payload,
            }
        )
        json_response = client.receive_json()
        final_data_in_db = find_in_collection(
            db, collection_name=_DEVICES_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
        )

        assert json_response["status"] == "success"
        json_response["data"].pop("id")
        assert json_response["data"] == final_data_in_db[0]

        created_at_timestamps = pop_field(final_data_in_db, "created_at")
        updated_at_timestamps = pop_field(final_data_in_db, "updated_at")

        assert original_data_in_db == []
        assert final_data_in_db == [payload]
        assert all([is_not_older_than(x, seconds=30) for x in created_at_timestamps])
        assert all([is_not_older_than(x, seconds=30) for x in updated_at_timestamps])


@pytest.mark.parametrize("payload", _DEVICE_LIST)
def test_create_device_wrong_cert(db, client, payload: Dict[str, Any], user_jwt_cookie):
    """Only clients with the certificate known to MSS can push to /devices/ws/{name}"""
    original_data_in_db = find_in_collection(
        db, collection_name=_DEVICES_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
    )

    name = payload["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers("WrongCert")

    with pytest.raises(WebSocketDisconnect) as exp:
        with client.websocket_connect(url, headers=headers):
            pass

    final_data_in_db = find_in_collection(
        db, collection_name=_DEVICES_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
    )

    assert exp.value.code == 1008
    assert exp.value.reason == "unauthorized"
    assert original_data_in_db == []
    assert final_data_in_db == []


@pytest.mark.parametrize("payload", _DEVICE_LIST)
def test_create_device_wrong_payload(
    db, client, payload: Dict[str, Any], user_jwt_cookie
):
    """BCC devices can only push their own device data to /devices/ws/{name} and not those of others"""
    original_data_in_db = find_in_collection(
        db, collection_name=_DEVICES_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
    )

    name = payload["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers(name)

    # using context manager to ensure on_startup runs
    with client.websocket_connect(url, headers=headers) as client:
        payload["name"] = f"{payload['name']}extra"
        client.send_json(
            {
                "status": "initialized",
                "data": payload,
            }
        )
        response = client.receive_json()
        final_data_in_db = find_in_collection(
            db, collection_name=_DEVICES_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
        )

        assert response == {
            "status": "error",
            "detail": f"forbidden: editing '{payload['name']}' is not allowed",
        }

        assert original_data_in_db == []
        assert final_data_in_db == []


@pytest.mark.parametrize("payload", _DEVICE_LIST)
def test_create_device_wrong_url(db, client, payload: Dict[str, Any], user_jwt_cookie):
    """BCC devices can only push to their own urls /devices/ws/{name}/ and not those of others"""
    original_data_in_db = find_in_collection(
        db, collection_name=_DEVICES_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
    )

    name = payload["name"]
    url = f"/devices/ws/{name}extra"
    headers = create_bcc_headers(name)

    with pytest.raises(WebSocketDisconnect) as exp:
        with client.websocket_connect(url, headers=headers):
            pass

    final_data_in_db = find_in_collection(
        db, collection_name=_DEVICES_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
    )

    assert exp.value.code == 1008
    assert exp.value.reason == "forbidden"
    assert original_data_in_db == []
    assert final_data_in_db == []


@pytest.mark.parametrize("backend_dict", _DEVICE_LIST)
def test_update_pre_existing_device(
    db, client, backend_dict: Dict[str, Any], system_app_token_header
):
    """Pushing 'initialized'-DeviceStatusMessage to /devices/ws/{name} a pre-existing device updates it"""
    insert_in_collection(db, collection_name=_DEVICES_COLLECTION, data=[backend_dict])
    original_data_in_db = find_in_collection(
        db, collection_name=_DEVICES_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
    )
    name = backend_dict["name"]
    url = f"/devices/ws/{name}"
    headers = create_bcc_headers(name)
    payload = {
        **backend_dict,
        "number_of_couplers": 100,
        "number_of_qubits": 80,
    }

    # using context manager to ensure on_startup runs
    with client.websocket_connect(url, headers=headers) as client:
        client.send_json(
            {
                "status": "initialized",
                "data": payload,
            }
        )
        json_response = client.receive_json()
        final_data_in_db = find_in_collection(
            db, collection_name=_DEVICES_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
        )

        assert json_response["status"] == "success"
        json_response["data"].pop("id")
        # when a device makes a connection, it sets last_online to None
        # but this 'last_online' property can be changed directly in payload
        if final_data_in_db[0]["last_online"] is None:
            del final_data_in_db[0]["last_online"]
        assert json_response["data"] == final_data_in_db[0]

        updated_at_timestamps = pop_field(final_data_in_db, "updated_at")
        expected = {
            **original_data_in_db[0],
            **payload,
        }

        assert original_data_in_db == [backend_dict]
        assert final_data_in_db[0] == expected
        assert all([is_not_older_than(x, seconds=30) for x in updated_at_timestamps])
