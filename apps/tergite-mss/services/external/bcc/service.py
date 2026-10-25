# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Clients for accessing certain HTTP services"""
import time
from datetime import datetime
from json import JSONDecodeError
from typing import Any, Dict, List, Literal, NotRequired, Optional, Tuple, TypedDict
from uuid import UUID

import httpx
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from loguru import logger

from libs.storage import Database
from services.auth import User
from services.external.bcc.dtos import (
    Booking,
    BookingsConfig,
    CancellationDetails,
    NewBCCUserInfo,
    NewBookingInfo,
    RecalibrationInfo,
)
from utils.api import GeneralMessage
from utils.config import BccConfig
from utils.crypto import decrypt_message, sign_message
from utils.exc import BccHttpError, ServiceUnavailableError, UnknownBccError

_BCC_CLIENTS: Dict[str, "BccClient"] = {}

BccClientHeaders = TypedDict(
    "BccClientHeaders",
    {
        "x-mss-request-id": str,
        "x-mss-timestamp": str,
        "x-mss-signature": str,
        "x-mss-user-id": str,
        "x-mss-is-admin": NotRequired[str],
    },
)
"""The headers sent via the BCC http client"""


async def create_clients(configs: List[BccConfig], private_key: RSAPrivateKey) -> None:
    """Creates the Bcc clients for the given BCC configs

    Args:
        configs: the configs for the Tergite backends
        private_key: the MSS private key, which signs every request to a BCC
    """
    global _BCC_CLIENTS
    await close_clients()
    _BCC_CLIENTS = {
        item.name: BccClient(
            f"{item.url}",
            name=item.name,
            public_base_url=f"{item.public_url}",
            private_key=private_key,
        )
        for item in configs
    }


async def close_clients():
    """Closes the Bcc clients"""
    for client in _BCC_CLIENTS.values():
        await client.close()

    _BCC_CLIENTS.clear()


def get_client(backend: str) -> "BccClient":
    """Gets the client of the BCC of the given name

    Args:
        backend: the name of the BCC

    Returns:
        the client of that BCC

    Raises:
        UnknownBccError: Unknown backend '{backend}'
    """
    try:
        return _BCC_CLIENTS[backend]
    except KeyError:
        raise UnknownBccError(f"Unknown backend '{backend}'")


class BccClient:
    """A client for making requests to a Backend Control Computer (BCC) Instance

    Attributes:
        name: name of the backend
        public_base_url: the base URL that can be accessed publicly
    """

    def __init__(
        self,
        base_url: str,
        name: str,
        public_base_url: str,
        private_key: RSAPrivateKey,
    ):
        self._client = httpx.AsyncClient(base_url=base_url)
        self.name = name
        self.public_base_url = public_base_url.rstrip("/")
        # MSS signs its requests to the BCC and decrypts the job tokens it gets with this key
        self._private_key = private_key

    async def get_token(
        self,
        job_id: str,
        user_id: str,
        request_id: str,
    ) -> Tuple[str, str]:
        """Retrieves the JWT for the given job_id and user_id from BCC

        Args:
            job_id: the id of the job
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request

        Returns:
            the pair of the encrypted JWT and the plain JWT

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: unauthenticated user
        """
        response = await self._request(
            "POST",
            "/token",
            user_id=user_id,
            request_id=request_id,
            json={"job_id": job_id, "user_id": user_id},
        )
        encrypted_token = response["access_token"]
        token = decrypt_message(self._private_key, msg=encrypted_token)
        return encrypted_token, token

    async def cancel_job(
        self,
        job_id: str | UUID,
        user_id: str,
        request_id: str,
        body: CancellationDetails,
        is_admin: Optional[bool] = None,
    ) -> GeneralMessage:
        """Attempts to cancel the job

        Args:
            job_id: the id of the job
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request
            body: the payload to post when cancelling
            is_admin: whether the user is an admin

        Returns:
            a general message showing status

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: unauthenticated user
        """
        payload = body.model_dump(mode="json")
        return await self._request(
            "POST",
            f"/jobs/{job_id}/cancel",
            user_id=user_id,
            request_id=request_id,
            json=payload,
            is_admin=is_admin,
        )

    async def delete_job(
        self,
        job_id: str | UUID,
        user_id: str,
        request_id: str,
        is_admin: Optional[bool] = None,
    ) -> GeneralMessage:
        """Attempts to delete the job

        Args:
            job_id: the id of the job
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request
            is_admin: whether the user is an admin

        Returns:
            a general message showing status

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: unauthenticated user
        """
        return await self._request(
            "DELETE",
            f"/jobs/{job_id}",
            user_id=user_id,
            request_id=request_id,
            is_admin=is_admin,
        )

    async def view_users(
        self,
        user_id: str,
        request_id: str,
        is_admin: Optional[bool] = None,
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> dict:
        """View list of users

        Args:
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request
            is_admin: whether the current user is an admin
            skip: the number of records to skip
            limit: the maximum number of records to return

        Returns:
            the paginated list of the available users

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: unauthenticated user
        """
        params: Dict[str, Any] = {"skip": skip}
        if limit is not None:
            params["limit"] = limit
        return await self._request(
            "GET",
            "/users",
            user_id=user_id,
            request_id=request_id,
            params=params,
            is_admin=is_admin,
        )

    async def create_user(
        self,
        user_id: str,
        request_id: str,
        data: NewBCCUserInfo,
        is_admin: Optional[bool] = None,
    ) -> dict:
        """Creates a user given the name and email

        Only MSS admin users can create users here

        Args:
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request
            data: the information about the new user
            is_admin: whether the current user is an admin

        Returns:
            the created user

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: unauthenticated user
        """
        return await self._request(
            "POST",
            "/users",
            user_id=user_id,
            request_id=request_id,
            json=data.model_dump(mode="json"),
            is_admin=is_admin,
        )

    async def delete_user(
        self,
        bcc_user_id: str | UUID,
        user_id: str,
        request_id: str,
        is_admin: Optional[bool] = None,
    ) -> GeneralMessage:
        """Attempts to delete the user

        Args:
            bcc_user_id: the id of the user
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request
            is_admin: whether the current user is an admin

        Returns:
            a general message showing status

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: unauthenticated user
        """
        return await self._request(
            "DELETE",
            f"/users/{bcc_user_id}",
            user_id=user_id,
            request_id=request_id,
            is_admin=is_admin,
        )

    async def create_booking(
        self,
        database: Database,
        user_id: str,
        request_id: str,
        data: NewBookingInfo,
        is_admin: Optional[bool] = None,
    ) -> Booking:
        """Creates a booking for the user of the given token

        Args:
            database: the database where the users are kept, to name them
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request
            data: the information about the new booking
            is_admin: whether the current user is an admin

        Returns:
            the newly created booking

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: unauthenticated user
        """
        booking = await self._request(
            "POST",
            "/bookings",
            user_id=user_id,
            request_id=request_id,
            json=data.model_dump(mode="json"),
            is_admin=is_admin,
        )
        user: User = await database.get(User, str(user_id))
        return Booking.model_validate(
            {**booking, "backend": self.name, "username": user.username}
        )

    async def cancel_booking(
        self,
        user_id: str,
        request_id: str,
        booking_id: str,
        is_admin: Optional[bool] = None,
    ) -> GeneralMessage:
        """Cancels a booking of given id for the user

        Args:
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request
            booking_id: the unique identifier of the booking to cancel
            is_admin: whether the current user is an admin

        Returns:
            the general message object with the status

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: unauthenticated user
        """
        return await self._request(
            "POST",
            f"/bookings/{booking_id}/cancel",
            user_id=user_id,
            request_id=request_id,
            is_admin=is_admin,
        )

    async def view_bookings(
        self,
        database: Database,
        requester_id: str,
        request_id: str,
        is_admin: Optional[bool] = None,
        skip: int = 0,
        limit: Optional[int] = None,
        min_start_utc: Optional[datetime] = None,
        max_start_utc: Optional[datetime] = None,
        user_id: Optional[str] = None,
        sort: Tuple[str, ...] = (),
    ) -> dict:
        """Views all available bookings

        Args:
            database: the database where the users are kept, to name them
            requester_id: the unique identifier of the user making this request
            request_id: the unique identifier of the current request
            is_admin: whether the current user is an admin
            skip: the number of records to skip
            limit: the maximum number of records to return
            min_start_utc: the minimum start time in UTC
            max_start_utc: the maximum start time in UTC
            user_id: the unique identifier of the owner of the given bookings
            sort: the fields to order by; prepending "-" returns the items in descending order of that field

        Returns:
            the paginated list of the available bookings filtered accordingly

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: unauthenticated user
        """
        params: Dict[str, Any] = {"skip": skip, "sort": sort}
        if limit is not None:
            params["limit"] = limit
        if min_start_utc is not None:
            params["min_start_utc"] = min_start_utc.isoformat()
        if max_start_utc is not None:
            params["max_start_utc"] = max_start_utc.isoformat()
        if user_id is not None:
            params["user_id"] = user_id

        response = await self._request(
            "GET",
            "/bookings",
            user_id=requester_id,
            request_id=request_id,
            params=params,
            is_admin=is_admin,
        )

        # add usernames
        user_ids = [v["user_id"] for v in response["data"] if v["user_id"] is not None]
        users = await database.find(User, filter={"id": {"$in": user_ids}})
        user_id_username_map = {user.id: user.username for user in users}
        for idx, booking in enumerate(response["data"]):
            booking["username"] = user_id_username_map.get(booking["user_id"])
            booking["backend"] = self.name
        return response

    async def view_bookings_configs(
        self,
        user_id: str,
        request_id: str,
        is_admin: Optional[bool] = None,
    ) -> BookingsConfig:
        """Views the configuration for the booking service in the backend

        Args:
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request
            is_admin: whether the current user is an admin

        Returns:
            the dict of configuration for the bookings service in this backend

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: unauthenticated user
        """
        response = await self._request(
            "GET",
            "/bookings/config",
            user_id=user_id,
            request_id=request_id,
            is_admin=is_admin,
        )
        return BookingsConfig.model_validate({**response, "backend": self.name})

    async def init_recalibration(
        self,
        user_id: str,
        request_id: str,
        is_admin: bool,
        start_timestamp: Optional[datetime] = None,
        interval: Optional[float] = None,
    ) -> GeneralMessage:
        """Initializes recalibration of the given backend

        Only MSS admin users can initialize recalibration

        Args:
            user_id: the ID of the user requesting this operation
            request_id: the unique identifier of the request
            is_admin: whether the current user is an admin
            start_timestamp: the start time of the recalibration; default = None i.e. straight away
            interval: the recalibration interval; default = None i.e. no repeat

        Returns:
            the status of the recalibration
        """
        params: Dict[str, Any] = {}
        if start_timestamp is not None:
            params["start_timestamp"] = start_timestamp.isoformat()
        if interval is not None:
            params["interval"] = interval

        response = await self._request(
            "POST",
            "/recalibration/init",
            user_id=user_id,
            request_id=request_id,
            is_admin=is_admin,
            params=params,
        )
        return response

    async def get_recalibration_info(
        self,
        user_id: str,
        request_id: str,
        is_admin: bool,
    ) -> RecalibrationInfo:
        """Gets the current information about the recalibration of the given backend

        Only MSS admin users can get recalibration info

        Args:
            user_id: the ID of the user requesting this operation
            request_id: the unique identifier of the request
            is_admin: whether the current user is an admin

        Returns:
            the information about the recalibration
        """
        response = await self._request(
            "GET",
            "/recalibration/info",
            user_id=user_id,
            request_id=request_id,
            is_admin=is_admin,
        )
        return response

    async def stop_recalibration(
        self,
        user_id: str,
        request_id: str,
        is_admin: bool,
        ignore_errors: Optional[bool] = None,
    ) -> GeneralMessage:
        """Cancels recalibration on this device

        Only MSS admin users can cancel recalibration

        Args:
            user_id: the ID of the user requesting this operation
            request_id: the unique identifier of the request
            is_admin: whether the current user is an admin
            ignore_errors: whether to ignore errors during recalibration

        Returns:
            general information on the status of the request
        """
        params: Dict[str, Any] = {}
        if ignore_errors is not None:
            params["ignore_errors"] = ignore_errors

        response = await self._request(
            "POST",
            "/recalibration/cancel",
            user_id=user_id,
            request_id=request_id,
            is_admin=is_admin,
            params=params,
        )
        return response

    async def switch_off(
        self,
        user_id: str,
        request_id: str,
        is_admin: bool,
    ) -> GeneralMessage:
        """Switches off this BCC device

        Only MSS admin users can switch off the device

        Args:
            user_id: the ID of the user requesting this operation
            request_id: the unique identifier of the request
            is_admin: whether the current user is an admin

        Returns:
            general information on the status of the request
        """

        response = await self._request(
            "POST",
            "/switch/off",
            user_id=user_id,
            request_id=request_id,
            is_admin=is_admin,
        )
        return response

    async def switch_on(
        self,
        user_id: str,
        request_id: str,
        is_admin: bool,
    ) -> GeneralMessage:
        """Switches on this BCC device

        Only MSS admin users can switch off the device

        Args:
            user_id: the ID of the user requesting this operation
            request_id: the unique identifier of the request
            is_admin: whether the current user is an admin

        Returns:
            general information on the status of the request
        """

        response = await self._request(
            "POST",
            "/switch/on",
            user_id=user_id,
            request_id=request_id,
            is_admin=is_admin,
        )
        return response

    async def _request(
        self,
        method: Literal["POST", "GET", "PUT", "DELETE", "PATCH"],
        url: str,
        user_id: str,
        request_id: str,
        json: Optional[dict] = None,
        params: Optional[Dict[str, Any]] = None,
        is_admin: Optional[bool] = None,
    ) -> dict:
        """Sends a request signed as MSS's to the BCC

        Args:
            method: the method to use when hitting the given URL.
            url: the route to hit
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request
            json: the payload to send
            params: the query params to add to the request
            is_admin: whether the request is from an admin user

        Returns:
            the BCC's JSON response

        Raises:
            ServiceUnavailableError: device is currently unavailable
            BccHttpError: the BCC answered with an HTTP error
        """
        try:
            headers = _create_headers(
                self._private_key,
                request_id=request_id,
                user_id=f"{user_id}",
                is_admin=is_admin,
            )
            logger.debug(f"Sending request to BCC: {method} {url}")
            response = await self._client.request(
                method, url, json=json, headers=headers, params=params
            )

            if response.is_error:
                message = _extract_error_message(response)
                logger.warning(
                    f"BCC returned HTTP error {response.status_code}: {message}"
                )
                raise BccHttpError(response.status_code, message)

            return response.json()
        except (httpx.ConnectError, httpx.TimeoutException):
            logger.exception("BCC connection failed")
            raise ServiceUnavailableError("device is currently unavailable")

    async def close(self):
        """Closes the client"""
        await self._client.aclose()


def _extract_error_message(response: httpx.Response) -> str:
    """Extracts the error message from the response

    Args:
        response: the response from requests

    Returns:
        the error message from the response
    """
    try:
        response_json = response.json()
        return response_json.get("detail")
    except JSONDecodeError:
        return response.text


def _create_headers(
    private_key: RSAPrivateKey,
    request_id: str,
    user_id: str = "",
    is_admin: Optional[bool] = None,
) -> BccClientHeaders:
    """Creates headers to show that the request is a valid one from MSS

    Args:
        private_key: the MSS private key
        request_id: the unique identifier of the current request
        user_id: the unique identifier of the user
        is_admin: whether the request should show that the user is an admin

    Returns:
        The dictionary of headers that show a given request is from MSS
    """
    timestamp = time.time()
    message = f"{user_id}-{request_id}-{timestamp}"
    signature = sign_message(private_key, message=message)
    headers = {
        "x-mss-request-id": request_id,
        "x-mss-timestamp": f"{timestamp}",
        "x-mss-signature": signature,
        "x-mss-user-id": user_id,
    }
    if is_admin is not None:
        headers["x-mss-is-admin"] = f"{is_admin}"

    return headers
