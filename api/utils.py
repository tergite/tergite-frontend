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

from dataclasses import dataclass
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from fastapi import Depends, WebSocketException
from loguru import logger
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.websockets import WebSocket

import settings
from libs.storage import Database
from services.bcc_nonces import claim_bcc_nonce
from utils.config import BccConfig, get_ip_addr
from utils.crypto import verify_ws_signature

from .database import get_database


async def get_verified_device_name(
    websocket: WebSocket, database: Database = Depends(get_database)
) -> str:
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
        headers = _read_signed_headers(websocket)
        backend_conf = settings.CONFIG.backends_dict[headers.name]
        _check_client_ip(websocket, backend_conf)
        verify_ws_signature(
            signature=headers.signature,
            message=f"{headers.name}-{headers.nonce}-{headers.timestamp}",
            key_path=backend_conf.public_key_path,
        )
        _check_nonce_age(
            float(headers.timestamp),
            now=datetime.now().timestamp(),
            ttl=settings.CONFIG.bcc_nonce_ttl,
        )
        # kept while its timestamp is fresh, after which _check_nonce_age refuses a replay
        await _check_nonce_unused(database, headers, ttl=settings.CONFIG.bcc_nonce_ttl)
        return headers.name
    except (KeyError, InvalidSignature, ValueError, AttributeError) as exp:
        logger.warning(f"WebSocket signature/nonce validation failed: {exp}")
        raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="unauthorized")


@dataclass(frozen=True)
class _SignedHeaders:
    name: str
    nonce: str
    timestamp: str
    signature: str


def _read_signed_headers(websocket: WebSocket) -> _SignedHeaders:
    """Reads the headers a BCC signs its websocket with

    Raises:
        KeyError: a header is missing
    """
    return _SignedHeaders(
        name=websocket.headers["x-id"],
        nonce=websocket.headers["x-request-id"],
        timestamp=websocket.headers["x-timestamp"],
        signature=websocket.headers["x-signature"],
    )


def _check_client_ip(websocket: WebSocket, backend_conf: BccConfig) -> str:
    """Gets the client's IP, checking it is the backend's if the backend asks for that

    Raises:
        ValueError: unexpected websocket client IP {client_ip}
    """
    client_ip = get_ip_addr(websocket.client.host)
    if backend_conf.is_strict_ip and client_ip != get_ip_addr(backend_conf.url.host):
        raise ValueError(f"unexpected websocket client IP {client_ip}")
    return client_ip


def _check_nonce_age(timestamp: float, now: float, ttl: float) -> None:
    """Checks the nonce's timestamp is neither older than ttl seconds nor in the future

    Raises:
        ValueError: the nonce is too old or from the future
    """
    age = now - timestamp
    if age > ttl:
        raise ValueError(
            f"nonce of timestamp {timestamp} is {age}s older than {ttl} seconds"
        )
    if age < 0:
        raise ValueError(f"timestamp {timestamp} is in the future")


async def _check_nonce_unused(
    database: Database, headers: _SignedHeaders, ttl: float
) -> None:
    """Claims the nonce, checking it was not used before

    Raises:
        ValueError: duplicate request nonce
    """
    is_new_nonce = await claim_bcc_nonce(database, headers.name, headers.nonce, ttl=ttl)
    if not is_new_nonce:
        raise ValueError(f"duplicate request nonce: '{headers.nonce}'")
