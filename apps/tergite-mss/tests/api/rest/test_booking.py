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
from typing import List

import pytest

from tests._utils.auth import TEST_USER_ID
from tests._utils.bcc import BookingPayload
from tests._utils.fixtures import load_json_fixture
from tests._utils.mock_backend import CREATED_BOOKINGS, VALID_BOOKING_PAYLOADS
from tests._utils.records import PaginationInfo, paginate
from tests.conftest import BACKEND_SLUGS

_PAGINATION: List[PaginationInfo] = load_json_fixture("pagination.json")

_FILTERS_AND_RESULTS = [
    ({}, CREATED_BOOKINGS),
    ({"min_start_utc": CREATED_BOOKINGS[1]["start_utc"]}, CREATED_BOOKINGS[1:]),
    ({"min_start_utc": CREATED_BOOKINGS[2]["start_utc"]}, CREATED_BOOKINGS[2:]),
    ({"max_start_utc": CREATED_BOOKINGS[1]["start_utc"]}, CREATED_BOOKINGS[:2]),
    (
        {
            "min_start_utc": CREATED_BOOKINGS[1]["start_utc"],
            "max_start_utc": CREATED_BOOKINGS[1]["start_utc"],
        },
        CREATED_BOOKINGS[1:2],
    ),
]
_BOOKINGS_CREATE_PARAMS = [
    (backend, payload)
    for backend in BACKEND_SLUGS
    for payload in VALID_BOOKING_PAYLOADS
]
_BOOKINGS_VIEW_PARAMS = [
    (backend, pagination, filters, expected_records)
    for backend in BACKEND_SLUGS
    for pagination in _PAGINATION
    for filters, expected_records in _FILTERS_AND_RESULTS
]
_BOOKINGS_CANCEL_PARAMS = [
    (backend, booking) for backend in BACKEND_SLUGS for booking in CREATED_BOOKINGS
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


@pytest.mark.parametrize("backend, payload", _BOOKINGS_CREATE_PARAMS)
def test_unauthenticated_create_booking(
    client, backend, payload: BookingPayload, mock_bcc
):
    """Creating booking without proper authentication errors out"""
    with client as client:
        headers = {"Authorization": f"Bearer {TEST_USER_ID}"}
        response = client.post(f"/bookings/{backend}", headers=headers, json=payload)

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

        response = client.post(f"/bookings/{backend}", json=payload)

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.parametrize(
    "backend, pagination, filters, expected_records", _BOOKINGS_VIEW_PARAMS
)
def test_view_bookings(
    client,
    backend,
    user_jwt_cookie,
    pagination: PaginationInfo,
    filters,
    expected_records,
    mock_bcc,
):
    """GET "/bookings/{backend}" shows paginated list of all available bookings"""
    with client as client:
        limit = pagination["limit"]
        skip = pagination["skip"]
        params = {k: v for k, v in pagination.items() if v is not None}
        params.update(filters)

        # view bookings
        response = client.get(
            f"/bookings/{backend}", cookies=user_jwt_cookie, params=params
        )
        actual_output = response.json()
        expected = paginate(expected_records, skip=skip, limit=limit)

        assert response.status_code == 200
        assert actual_output == expected


@pytest.mark.parametrize(
    "backend, pagination, filters, expected_records", _BOOKINGS_VIEW_PARAMS
)
def test_unauthenticated_view_bookings(
    client, backend, pagination: PaginationInfo, filters, expected_records, mock_bcc
):
    """Viewing bookings without authenticated user errors out"""
    with client as client:
        headers = {"Authorization": f"Bearer {TEST_USER_ID}"}
        url = f"/bookings/{backend}"
        params = {k: v for k, v in pagination.items() if v is not None}
        params.update(filters)
        response = client.get(url, headers=headers, params=params)

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

        response = client.get(url, params=params)

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}


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


@pytest.mark.parametrize("backend, booking", _BOOKINGS_CANCEL_PARAMS)
def test_unauthenticated_cancel_booking(client, backend, booking, mock_bcc):
    """Cancelling booking without proper authentication errors out"""
    with client as client:
        booking_id = booking["id"]
        headers = {"Authorization": f"Bearer {TEST_USER_ID}"}
        url = f"/bookings/{backend}/{booking_id}/cancel"
        response = client.post(url, headers=headers)

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}

        response = client.post(url)

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
