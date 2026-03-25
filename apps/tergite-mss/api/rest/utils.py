# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023, 2024
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Miscellaneous utility functions for the routers"""

import logging
import uuid
from datetime import datetime
from typing import Dict

from cryptography.exceptions import InvalidSignature
from fastapi import Depends, WebSocketException
from starlette.requests import Request
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.websockets import WebSocket

import settings
from services.external import bcc
from utils.api import get_request_logs_store, verify_ws_signature
from utils.config import get_ip_addr
from utils.exc import InvalidRequestIDError, UnknownBccError
from utils.mongodb import get_mongodb


async def get_request_id(request: Request) -> str:
    """Extracts value of the X-Request-ID header

    Args:
        request: the FastAPI request object

    Returns:
        the string in the X-Request-ID

    Raises:
        InvalidRequestIDError: "No request ID provided"
        InvalidRequestIDError: "The request ID '{request_id}' is not a valid UUID4"
    """
    try:
        request_id = request.state.request_id
        if not _is_valid_uuid4(request_id):
            raise InvalidRequestIDError(
                f"The request ID '{request_id}' is not a valid UUID4"
            )
        return request_id
    except AttributeError:
        raise InvalidRequestIDError(f"The request ID '' is not a valid UUID4")


def get_verified_device_name(websocket: WebSocket) -> str:
    """Returns the device name as got from BCC passed through special headers

    We are choosing to trust BCC and so whenever a request comes from
    BCC, there will be an `x-id` and `x-signature` header.
    We will get the `x-id` and return it only if the `x-signature`
    is verified by BCC public key and the client host is what is expected by MSS.

    For better security against replay attacks, we also use the `x-request-id` and
    `x-timestamp` headers

    Args:
        websocket: the current FastAPI websocket request

    Returns:
        the name of the device

    Raises:
        NotAuthenticatedError: user not authenticated
    """
    try:
        name = websocket.headers["x-id"]
        nonce = websocket.headers["x-request-id"]
        timestamp = websocket.headers["x-timestamp"]
        signature = websocket.headers["x-signature"]
        backend_conf = settings.CONFIG.backends_dict[name]

        client_ip = get_ip_addr(websocket.client.host)
        if (
            backend_conf.is_strict_ip
            and settings.CONFIG.client_ip != backend_conf.ip_address
        ):
            raise ValueError(f"unexpected websocket client IP {client_ip}")

        message = f"{name}-{nonce}-{timestamp}"
        verify_ws_signature(
            signature=signature,
            message=message,
            key_path=backend_conf.public_key_path,
        )

        current_timestamp = datetime.now().timestamp()
        timestamp_float = float(timestamp)
        time_difference = current_timestamp - timestamp_float
        if time_difference > settings.CONFIG.bcc_nonce_ttl:
            raise ValueError(
                f"nonce of timestamp {timestamp} is {time_difference}s older than {settings.CONFIG.bcc_nonce_ttl} seconds"
            )
        elif time_difference < 0:
            raise ValueError(f"timestamp {timestamp} is in the future")

        requests_store = get_request_logs_store()
        if requests_store.exists(nonce):
            raise ValueError(f"duplicate request nonce: '{nonce}'")

        return name
    except (KeyError, InvalidSignature, ValueError, AttributeError) as exp:
        logging.error(exp)
        raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="unauthorized")


def _is_valid_uuid4(value):
    """Validates the given string is a valid UUID4

    Args:
        value: the value to validate

    Returns:
        True if the value is a valid UUID4 string else false
    """
    try:
        temp_uuid = uuid.UUID(value, version=4)
    except (ValueError, TypeError):
        return False
    return str(temp_uuid) == value


async def get_default_mongodb():
    return get_mongodb(
        url=f"{settings.CONFIG.database.url}", name=settings.CONFIG.database.name
    )


async def get_bcc_client(
    backend: str,
    bcc_clients_map: Dict[str, bcc.BccClient] = Depends(bcc.get_client_map),
) -> bcc.BccClient:
    """Dependency injector to return the BCC client

    Args:
        backend (str): the name of the backend
        bcc_clients_map (BccClientsMap): the map of BCC clients

    Returns:
        bcc.BccClient: the BCC client

    Raises:
        UnknownBccError: Unknown backend '{backend}'
    """
    try:
        return bcc_clients_map[backend]
    except KeyError:
        raise UnknownBccError(f"Unknown backend '{backend}'")
