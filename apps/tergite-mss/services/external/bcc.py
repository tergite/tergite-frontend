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
import logging
import time
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, List, NotRequired, Optional, Tuple, TypedDict

import httpx

from settings import PRIVATE_KEY_FILE
from utils.config import BccConfig
from utils.crypto import decrypt_message, sign_message
from utils.exc import ServiceUnavailableError

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


async def create_clients(configs: List[BccConfig]):
    """Creates the Bcc clients for the given BCC configs

    Args:
        configs: the configs for the Tergite backends
    """
    global _BCC_CLIENTS
    await close_clients()
    _BCC_CLIENTS = {item.name: BccClient(base_url=f"{item.url}") for item in configs}


async def close_clients():
    """Closes the Bcc clients"""
    global _BCC_CLIENTS
    for client in _BCC_CLIENTS.values():
        await client.close()

    _BCC_CLIENTS.clear()


def get_client_map() -> Dict[str, "BccClient"]:
    """Get the map of Bcc Clients, where the key is the name of the BCC instance

    This is quite useful as a dependency injector
    """
    return _BCC_CLIENTS


class BccClient:
    """A client for making requests to a Backend Control Computer (BCC) Instance

    Attributes:
        base_url: the base URL for the given BCC instance
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=base_url)

    async def get_token(
        self,
        job_id: str,
        user_id: str,
        request_id: str,
        private_key_file=PRIVATE_KEY_FILE,
    ) -> Tuple[str, str]:
        """Retrieves the JWT for the given job_id and user_id from BCC

        Args:
            job_id: the id of the job
            user_id: the app token associated with the job id
            request_id: the unique identifier of the current request
            private_key_file: the path to the private key file

        Returns:
            the pair of the encrypted JWT and the plain JWT

        Raises:
            ServiceUnavailableError: device is currently unavailable
            ValueError: unauthenticated user
        """
        try:
            headers = _create_headers(
                private_key_file=private_key_file,
                request_id=request_id,
                user_id=user_id,
            )
            response = await self._client.post(
                "/token", json={"job_id": job_id, "user_id": user_id}, headers=headers
            )

            if response.is_error:
                message = _extract_error_message(response)
                raise ValueError(message)

            encrypted_token = response.json()["access_token"]
            token = decrypt_message(
                private_key_file=private_key_file, msg=encrypted_token
            )

            return encrypted_token, token
        except (httpx.ConnectError, httpx.ConnectTimeout) as exp:
            logging.error(exp)
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
        return response_json.get("detail", response_json)
    except JSONDecodeError:
        return response.text


def _create_headers(
    private_key_file: Path,
    request_id: str,
    user_id: str = "",
    is_admin: Optional[bool] = None,
) -> BccClientHeaders:
    """Creates headers to show that the request is a valid one from MSS

    Args:
        private_key_file: the path to the private key file
        request_id: the unique identifier of the current request
        user_id: the unique identifier of the user
        is_admin: whether the request should show that the user is an admin

    Returns:
        The dictionary of headers that show a given request is from MSS
    """
    timestamp = time.time()
    message = f"{user_id}-{request_id}-{timestamp}"
    signature = sign_message(private_key_file, message=message)
    headers = {
        "x-mss-request-id": request_id,
        "x-mss-timestamp": f"{timestamp}",
        "x-mss-signature": signature,
        "x-mss-user-id": user_id,
    }
    if is_admin is not None:
        headers["x-mss-is-admin"] = f"{is_admin}"

    return headers
