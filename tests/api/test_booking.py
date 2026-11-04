# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for the booking endpoints"""

from typing import Dict, List

import pytest

from tests._utils.auth import (
    TEST_SUPERUSER_EMAIL,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_EMAIL,
    TEST_SYSTEM_USER_ID,
    TEST_USER_EMAIL,
    TEST_USER_ID,
)
from tests._utils.bcc import BookingPayload
from tests._utils.fixtures import load_json_fixture
from tests._utils.mock_backend import (
    BOOKINGS_CONFIG,
    CREATED_BOOKINGS,
    VALID_BOOKING_PAYLOADS,
)
from tests._utils.records import PaginationInfo, order_by, paginate
from tests.conftest import BACKEND_SLUGS

_PAGINATION: List[PaginationInfo] = load_json_fixture("pagination.json")
_USERNAMES_MAP: Dict[str, str] = {
    TEST_USER_ID: TEST_USER_EMAIL.split("@")[0],
    TEST_SYSTEM_USER_ID: TEST_SYSTEM_USER_EMAIL.split("@")[0],
    TEST_SUPERUSER_ID: TEST_SUPERUSER_EMAIL.split("@")[0],
}
BOOKINGS_IN_MSS = [
    {**v, "username": _USERNAMES_MAP[v["user_id"]]} for v in CREATED_BOOKINGS
]
_sort_by_start = lambda data, desc: order_by(data, "start_utc", desc)
_sort_by_usr = lambda data: order_by(data, "user_id")

_FILTERS_SORT_AND_RESULTS = [
    ({}, (), BOOKINGS_IN_MSS),
    ({}, ("-start_utc",), _sort_by_start(BOOKINGS_IN_MSS, desc=True)),
    ({"min_start_utc": BOOKINGS_IN_MSS[1]["start_utc"]}, (), BOOKINGS_IN_MSS[1:]),
    ({"min_start_utc": BOOKINGS_IN_MSS[2]["start_utc"]}, (), BOOKINGS_IN_MSS[2:]),
    (
        {"min_start_utc": BOOKINGS_IN_MSS[2]["start_utc"], "user_id": TEST_USER_ID},
        (),
        [v for v in BOOKINGS_IN_MSS[2:] if v["user_id"] == TEST_USER_ID],
    ),
    ({"max_start_utc": BOOKINGS_IN_MSS[1]["start_utc"]}, (), BOOKINGS_IN_MSS[:2]),
    (
        {"max_start_utc": BOOKINGS_IN_MSS[1]["start_utc"]},
        ("user_id",),
        _sort_by_usr(BOOKINGS_IN_MSS[:2]),
    ),
    (
        {
            "max_start_utc": BOOKINGS_IN_MSS[1]["start_utc"],
            "user_id": TEST_SYSTEM_USER_ID,
        },
        (),
        [v for v in BOOKINGS_IN_MSS[:2] if v["user_id"] == TEST_SYSTEM_USER_ID],
    ),
    (
        {"user_id": TEST_SYSTEM_USER_ID},
        (),
        [v for v in BOOKINGS_IN_MSS if v["user_id"] == TEST_SYSTEM_USER_ID],
    ),
    (
        {
            "min_start_utc": BOOKINGS_IN_MSS[1]["start_utc"],
            "max_start_utc": BOOKINGS_IN_MSS[1]["start_utc"],
        },
        (),
        BOOKINGS_IN_MSS[1:2],
    ),
]
# every case on the first backend; the second only shows a route reaches its own BCC
_BACKEND, _OTHER_BACKEND = BACKEND_SLUGS
_BOOKINGS_CREATE_PARAMS = [
    *((_BACKEND, payload) for payload in VALID_BOOKING_PAYLOADS),
    (_OTHER_BACKEND, VALID_BOOKING_PAYLOADS[0]),
]
_NO_PAGINATION: PaginationInfo = {"skip": 0, "limit": None}
_BOOKINGS_VIEW_PARAMS = [
    *(
        (_BACKEND, _NO_PAGINATION, filters, sort, expected_records)
        for filters, sort, expected_records in _FILTERS_SORT_AND_RESULTS
    ),
    *(
        (_BACKEND, pagination, {}, (), BOOKINGS_IN_MSS)
        for pagination in _PAGINATION
        if pagination != _NO_PAGINATION
    ),
    (_OTHER_BACKEND, _NO_PAGINATION, {}, (), BOOKINGS_IN_MSS),
]
_BOOKINGS_CANCEL_PARAMS = [
    *((_BACKEND, booking) for booking in CREATED_BOOKINGS),
    (_OTHER_BACKEND, CREATED_BOOKINGS[0]),
]
_BOOKING_ROUTES = [
    ("post", f"/bookings/{_BACKEND}", VALID_BOOKING_PAYLOADS[0]),
    ("get", f"/bookings/{_BACKEND}", None),
    ("post", f"/bookings/{_BACKEND}/{CREATED_BOOKINGS[0]['id']}/cancel", None),
    ("get", f"/bookings/{_BACKEND}/config", None),
]


@pytest.mark.parametrize("backend, payload", _BOOKINGS_CREATE_PARAMS)
def test_create_booking(
    client, user_jwt_cookie, backend, payload: BookingPayload, mock_bcc
):
    """POST '/bookings/{backend}' should return the new booking created by the user"""
    with client as client:
        response = client.post(
            f"/bookings/{backend}", json=payload, cookies=user_jwt_cookie
        )
        actual_booking = response.json()

        assert response.status_code == 200

        assert actual_booking["id"] != ""
        assert actual_booking["start_utc"] == payload["start_utc"]
        assert actual_booking["end_utc"] == payload["end_utc"]
        assert actual_booking["user_id"] == TEST_USER_ID
        assert actual_booking["username"] == _USERNAMES_MAP[TEST_USER_ID]
        assert actual_booking["backend"] == backend


@pytest.mark.parametrize(
    "backend, pagination, filters, sort, expected_records", _BOOKINGS_VIEW_PARAMS
)
def test_view_bookings(
    client,
    backend,
    user_jwt_cookie,
    pagination: PaginationInfo,
    filters,
    sort,
    expected_records,
    mock_bcc,
):
    """GET "/bookings/{backend}" shows paginated list of all available bookings"""
    with client as client:
        limit = pagination["limit"]
        skip = pagination["skip"]
        params = {k: v for k, v in pagination.items() if v is not None}
        params.update(filters)
        params.update({"sort": sort})

        # view bookings
        response = client.get(
            f"/bookings/{backend}", cookies=user_jwt_cookie, params=params
        )
        actual_output = response.json()
        expected_records = [{**v, "backend": backend} for v in expected_records]
        expected = paginate(expected_records, skip=skip, limit=limit)

        assert response.status_code == 200
        assert actual_output == expected


@pytest.mark.parametrize("backend, booking", _BOOKINGS_CANCEL_PARAMS)
def test_cancel_future_booking(client, backend, booking, user_jwt_cookie, mock_bcc):
    """POST '/bookings/{backend}/{id}/cancel' for a future booking, deletes the booking and allows jobs to run without it."""
    with client as client:
        booking_id = booking["id"]
        response = client.post(
            f"/bookings/{backend}/{booking_id}/cancel", cookies=user_jwt_cookie
        )
        expected = {
            "status": "success",
            "detail": f"Booking of id {booking_id} cancelled",
        }
        got = response.json()

        assert response.status_code == 200
        assert got == expected


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_view_bookings_config(client, backend, user_jwt_cookie, mock_bcc):
    """GET "/bookings/config" shows paginated list of all available bookings"""
    with client as client:
        response = client.get(f"/bookings/{backend}/config", cookies=user_jwt_cookie)
        got = response.json()
        expected = {**BOOKINGS_CONFIG, "backend": backend}
        assert got == expected


@pytest.mark.parametrize("method, url, payload", _BOOKING_ROUTES)
def test_unauthenticated_booking_routes(client, method, url, payload, mock_bcc):
    """Every booking route refuses a request without a valid user"""
    with client as client:
        headers = {"Authorization": f"Bearer {TEST_USER_ID}"}
        response = client.request(method, url, headers=headers, json=payload)

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

        response = client.request(method, url, json=payload)

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
