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
"""Utilities for mocking requests to BCC"""
import json
import re
from datetime import datetime
from json import JSONDecodeError
from typing import List

import httpx

from services.external.bcc.dtos import (
    BCCUserProfile,
    CancellationDetails,
)
from tests._utils.auth import (
    TEST_SUPERUSER_DICT,
    TEST_SYSTEM_USER_DICT,
    TEST_SYSTEM_USER_ID,
    TEST_USER_DICT,
    TEST_USER_ID,
)
from tests._utils.bcc import (
    BasicBookingInfo,
    BookingPayload,
    CreatedBooking,
    create_bcc_client_jwt_token,
    encrypt_jwt_token,
    get_bcc_client_verified_headers,
    to_booking_payload,
)
from tests._utils.fixtures import load_json_fixture
from tests._utils.records import order_by_many, paginate
from utils.config import UserRole

_USERS = [TEST_USER_DICT, TEST_SYSTEM_USER_DICT, TEST_SUPERUSER_DICT]
BCC_USERS = [
    {
        "email": v["email"],
        "id": str(v["_id"]),
        "name": v["email"],
        "is_admin": UserRole.ADMIN in v["roles"],
    }
    for v in _USERS
]
VALID_BOOKINGS: List[BasicBookingInfo] = load_json_fixture("valid_bookings.json")
INVALID_BOOKINGS: List[BasicBookingInfo] = load_json_fixture("invalid_bookings.json")

VALID_BOOKING_PAYLOADS: List[BookingPayload] = [
    to_booking_payload(v) for v in VALID_BOOKINGS
]
_FIRST_USER_ID = _USERS[0]["_id"]
CREATED_BOOKINGS: List[dict] = [
    CreatedBooking(**v, user_id=TEST_USER_ID).model_dump(mode="json")
    if idx % 2 == 0
    else CreatedBooking(**v, user_id=TEST_SYSTEM_USER_ID).model_dump(mode="json")
    for idx, v in enumerate(VALID_BOOKING_PAYLOADS)
]
BOOKINGS_CONFIG = dict(
    max_time_slot_length=1200,
    min_time_slot_length=100,
    max_slots_per_day=80,
    max_idle_time=100,
)


def get_token(request: httpx.Request):
    """Mock BCC token endpoint

    Args:
        request: the httpx request

    Returns:
        dict of access token and type
    """
    try:
        headers = get_bcc_client_verified_headers(request)
        body = json.loads(request.content)
        assert headers["x-mss-user-id"] == body["user_id"]
        token = create_bcc_client_jwt_token(**body)
        encrypted_token = encrypt_jwt_token(token)
        return httpx.Response(
            status_code=200,
            json={"access_token": encrypted_token, "token_type": "bearer"},
        )
    except ValueError as exp:
        return httpx.Response(
            status_code=401, json={"detail": f"user not authenticated {exp}"}
        )
    except (KeyError, JSONDecodeError, TypeError, AssertionError) as exp:
        return httpx.Response(
            status_code=400, json={"detail": f"malformed request body {exp}"}
        )
    except Exception as exp:
        raise exp


def delete_job(request: httpx.Request):
    """Mock BCC job deletion endpoint

    Args:
        request: the httpx request

    Returns:
        dict of status and detail
    """
    try:
        job_id = re.match(r"^.*/jobs/(.*)$", f"{request.url}").group(1)
        get_bcc_client_verified_headers(request)
        return httpx.Response(
            status_code=200,
            json={"status": "success", "detail": f"Job of id {job_id} deleted"},
        )
    except (ValueError, AssertionError) as exp:
        return httpx.Response(
            status_code=401, json={"detail": f"user not authenticated {exp}"}
        )
    except Exception as exp:
        raise exp


def cancel_job(request: httpx.Request):
    """Mock BCC job cancellation endpoint

    Args:
        request: the httpx request

    Returns:
        dict of status and detail
    """
    try:
        job_id = re.match(r"^.*/jobs/(.*)/cancel$", f"{request.url}").group(1)
        get_bcc_client_verified_headers(request)
        body = CancellationDetails.model_validate_json(request.content)
        # FIXME: We don't check anything, we just always just cancel. We could have checked if admin or owner but
        #   that would almost be a full app and would require this function to have access to the database.
        return httpx.Response(
            status_code=200,
            json={"status": "success", "detail": f"Job of id {job_id} cancelled"},
        )
    except ValueError as exp:
        return httpx.Response(
            status_code=401, json={"detail": f"user not authenticated {exp}"}
        )
    except (KeyError, JSONDecodeError, TypeError) as exp:
        return httpx.Response(
            status_code=400, json={"detail": f"malformed request body {exp}"}
        )
    except Exception as exp:
        raise exp


def create_user(request: httpx.Request):
    """Mock BCC users create endpoint

    Args:
        request: the httpx request

    Returns:
        the response containing the created user
    """
    try:
        headers = get_bcc_client_verified_headers(request)
        assert headers["x-mss-is-admin"] == "True"
        user_profile = BCCUserProfile.model_validate_json(request.content)
        return httpx.Response(
            status_code=200,
            json=user_profile.model_dump(),
        )
    except (KeyError, AssertionError):
        return httpx.Response(status_code=403, json={"detail": "Forbidden"})
    except ValueError as exp:
        return httpx.Response(
            status_code=401, json={"detail": f"user not authenticated {exp}"}
        )
    except (JSONDecodeError, TypeError) as exp:
        return httpx.Response(
            status_code=400, json={"detail": f"malformed request body {exp}"}
        )
    except Exception as exp:
        raise exp


def view_users(request: httpx.Request):
    """Mock BCC users view endpoint

    Args:
        request: the httpx request

    Returns:
        the response paginated users
    """
    try:
        headers = get_bcc_client_verified_headers(request)
        assert headers["x-mss-is-admin"] == "True"

        skip = request.url.params.get("skip") or "0"
        skip = int(skip)
        limit = request.url.params.get("limit") or None
        if limit is not None:
            limit = int(limit)

        users = [
            BCCUserProfile.model_validate(v).model_dump(mode="json") for v in BCC_USERS
        ]
        result = paginate(users, skip=skip, limit=limit)
        return httpx.Response(
            status_code=200,
            json=result,
        )
    except (KeyError, AssertionError):
        return httpx.Response(status_code=403, json={"detail": "Forbidden"})
    except ValueError as exp:
        return httpx.Response(
            status_code=401, json={"detail": f"user not authenticated {exp}"}
        )
    except Exception as exp:
        raise exp


def delete_users(request: httpx.Request):
    """Mock BCC users delete endpoint

    Args:
        request: the httpx request

    Returns:
        the response of status message
    """
    try:
        headers = get_bcc_client_verified_headers(request)
        assert headers["x-mss-is-admin"] == "True"

        return httpx.Response(
            status_code=200,
            json={"status": "success", "detail": "User deleted"},
        )
    except (KeyError, AssertionError):
        return httpx.Response(status_code=403, json={"detail": "Forbidden"})
    except ValueError as exp:
        return httpx.Response(
            status_code=401, json={"detail": f"user not authenticated {exp}"}
        )
    except Exception as exp:
        raise exp


def create_booking(request: httpx.Request):
    """Mock BCC booking create endpoint

    Args:
        request: the httpx request

    Returns:
        the response containing the created booking
    """
    try:
        headers = get_bcc_client_verified_headers(request)
        user_id = headers["x-mss-user-id"]
        booking = CreatedBooking.model_validate_json(request.content)
        booking.user_id = user_id
        return httpx.Response(
            status_code=200,
            json=booking.model_dump(mode="json"),
        )
    except (KeyError, ValueError) as exp:
        return httpx.Response(
            status_code=401, json={"detail": f"user not authenticated {exp}"}
        )
    except (JSONDecodeError, TypeError) as exp:
        return httpx.Response(
            status_code=400, json={"detail": f"malformed request body {exp}"}
        )
    except Exception as exp:
        raise exp


def view_bookings(request: httpx.Request):
    """Mock BCC bookings view endpoint

    Args:
        request: the httpx request

    Returns:
        the response with paginated bookings
    """
    try:
        get_bcc_client_verified_headers(request)
        skip = request.url.params.get("skip") or "0"
        skip = int(skip)
        limit = request.url.params.get("limit") or None
        if limit is not None:
            limit = int(limit)

        min_start_utc = request.url.params.get("min_start_utc") or None
        max_start_utc = request.url.params.get("max_start_utc") or None
        user_id = request.url.params.get("user_id") or None
        sort = request.url.params.get("sort") or ()
        if isinstance(sort, str):
            sort = (sort,)

        filtered_results = CREATED_BOOKINGS

        if min_start_utc is not None:
            filtered_results = [
                v
                for v in filtered_results
                if datetime.fromisoformat(v["start_utc"])
                >= datetime.fromisoformat(min_start_utc)
            ]

        if max_start_utc is not None:
            filtered_results = [
                v
                for v in filtered_results
                if datetime.fromisoformat(v["start_utc"])
                <= datetime.fromisoformat(max_start_utc)
            ]

        if user_id is not None:
            filtered_results = [v for v in filtered_results if v["user_id"] == user_id]

        filtered_results = order_by_many(filtered_results, sort)
        result = paginate(filtered_results, skip=skip, limit=limit)
        return httpx.Response(
            status_code=200,
            json=result,
        )
    except ValueError as exp:
        return httpx.Response(
            status_code=401, json={"detail": f"user not authenticated {exp}"}
        )
    except Exception as exp:
        raise exp


def cancel_booking(request: httpx.Request):
    """Mock BCC booking cancellation endpoint

    Args:
        request: the httpx request

    Returns:
        dict of status and detail
    """
    try:
        booking_id = re.match(r"^.*/bookings/(.*)/cancel$", f"{request.url}").group(1)
        get_bcc_client_verified_headers(request)
        # FIXME: We don't check anything, we just always just cancel. We could have checked if admin or owner but
        #   that would almost be a full app and would require this function to have access to the database.
        return httpx.Response(
            status_code=200,
            json={
                "status": "success",
                "detail": f"Booking of id {booking_id} cancelled",
            },
        )
    except ValueError as exp:
        return httpx.Response(
            status_code=401, json={"detail": f"user not authenticated {exp}"}
        )
    except (KeyError, TypeError) as exp:
        return httpx.Response(
            status_code=400, json={"detail": f"malformed request {exp}"}
        )
    except Exception as exp:
        raise exp


def view_bookings_config(request: httpx.Request):
    """Mock BCC bookings config view endpoint

    Args:
        request: the httpx request

    Returns:
        the response with the bookings config
    """
    try:
        get_bcc_client_verified_headers(request)
        return httpx.Response(
            status_code=200,
            json=BOOKINGS_CONFIG,
        )
    except ValueError as exp:
        return httpx.Response(
            status_code=401, json={"detail": f"user not authenticated {exp}"}
        )
    except Exception as exp:
        raise exp
