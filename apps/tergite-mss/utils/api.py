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
"""Utility functions for API related code"""
import base64
import logging
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    NotRequired,
    Optional,
    TypedDict,
    TypeVar,
    Union,
)

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from fastapi import HTTPException, Response, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.requests import Request
from fastapi.websockets import WebSocket
from pydantic import BaseModel, ConfigDict, Field
from pydantic.main import IncEx
from redis import Redis

import settings
from utils.crypto import get_uuid4_str
from utils.date_time import get_current_timestamp
from utils.logging import err_logger as access_logger
from utils.redis_store import Collection, Schema

ITEM = TypeVar("ITEM", bound=BaseModel)
_BCC_PUBLIC_KEYS: Dict[str, RSAPublicKey] = {}
_REQUEST_LOGS_STORE: Optional[Collection["WebsocketRequestLog"]] = None


class PaginatedListResponse(BaseModel, Generic[ITEM]):
    """The response when sending paginated data"""

    skip: int = 0
    limit: Optional[int] = None
    data: List[ITEM] = []

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_data_none_fields: bool = True,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        fallback: Callable[[Any], Any] | None = None,
        serialize_as_any: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        return {
            "skip": self.skip,
            "limit": self.limit,
            "data": [
                item.model_dump(
                    mode=mode,
                    include=include,
                    exclude=exclude,
                    context=context,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_defaults=exclude_defaults,
                    exclude_none=exclude_data_none_fields,
                    round_trip=round_trip,
                    warnings=warnings,
                    fallback=fallback,
                    serialize_as_any=serialize_as_any,
                )
                for item in self.data
            ],
        }


class GeneralMessage(TypedDict):
    """A general message object sent on the API"""

    status: Literal["success", "error", "cancelled", "failed"]
    detail: NotRequired[str]
    data: NotRequired[dict | list]


class WebsocketRequestLog(Schema):
    """Schema for tracking websocket requests"""

    __primary_key_fields__ = ("request_id",)
    __index_fields__ = (
        "id",
        "ip_address",
    )
    model_config = ConfigDict(extra="allow")

    request_id: str
    id: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    @classmethod
    def from_request(cls, websocket: WebSocket) -> "WebsocketRequestLog":
        """Generates a request log object from the request

        Args:
            websocket: the received HTTP request

        Returns:
            the request log object
        """
        request_id = websocket.headers.get("x-request-id", websocket.state.request_id)
        return cls(
            request_id=request_id,
            id=websocket.headers.get("x-id"),
            ip_address=f"{websocket.client.host}",
        )


class EventResponse(GeneralMessage):
    """Response to an event"""

    id: str


class WebsocketConnectionManager:
    """Manages connections to a websockets endpoint"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Allows a connection to be established"""
        request_id = websocket.headers.get("x-request-id")
        if request_id is None:
            request_id = get_uuid4_str()

        websocket.state.request_id = request_id
        requests_store = get_request_logs_store()
        if not requests_store.exists(request_id):
            requests_store.insert(WebsocketRequestLog.from_request(websocket))

        await websocket.accept(headers=[(b"x-request-id", request_id.encode("utf8"))])
        self.active_connections.append(websocket)
        access_logger.info(
            "Connected: %s at %s", websocket.client.host, str(websocket.url)
        )

    def disconnect(self, websocket: WebSocket):
        """Removes a given websocket connection"""
        self.active_connections.remove(websocket)
        access_logger.info(
            "Disconnected: %s at %s", websocket.client.host, str(websocket.url)
        )

    async def reply(self, websocket: WebSocket, message: EventResponse):
        """Sends a message to the given websocket"""
        await websocket.send_json(message)

    async def broadcast(self, message: str):
        """Broadcasts a message to all connections on a websocket endpoint"""
        for connection in self.active_connections:
            await connection.send_text(message)

    async def close_all(self, reason: str = "Server closing connection"):
        """Closes all active connections

        Args:
            reason: Reason for closing the connection
        """
        for connection in list(self.active_connections):
            access_logger.info(
                f"Closing: %s at %s", connection.client.host, str(connection.url)
            )
            await connection.close(code=1001, reason=reason)


def get_bearer_token(request: Request, raise_if_error: bool = True) -> Optional[str]:
    """Extracts the bearer token from the request or throws a 401 exception if not exist and `raise_if_error` is True

    Args:
        request: the request object from FastAPI
        raise_if_error: whether an error should be raised if it occurs

    Raises:
        HTTPException: Unauthorized

    Returns:
        the bearer token as a string or None if it does not exist and `raise_if_error` is False
    """
    try:
        authorization_header = request.headers["Authorization"]
        return authorization_header.split("Bearer ")[1].strip()
    except (KeyError, IndexError):
        if raise_if_error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


def to_http_error(
    status_code: int, custom_message: Optional[str] = None
) -> Callable[[Request, Exception], Union[Response, Awaitable[Response]]]:
    """An error handler that converts the exception to an HTTPException

    The details in the http error are got from the exception itself.
    It also logs the original error.

    Args:
        status_code: the HTTP status code
        custom_message: a custom message to send to the client

    Returns:
        an HTTP exception handler function
    """

    async def handler(request: Request, exp: Exception) -> Response:
        logging.error(exp)
        message = custom_message
        if message is None:
            message = f"{exp}"

        http_exp = HTTPException(status_code, message)
        return await http_exception_handler(request, http_exp)

    return handler


def verify_ws_signature(signature: str, message: str, key_path: Path) -> None:
    """Verifies that the given message is from an approved source, given the signature

    Args:
        signature: the signature of the message signed by BCC
        message: the message from MSS
        key_path: the file path to the RSA public key PEM file

    Raises:
        InvalidSignature: if signature does not match with what would be expected from MSS
    """
    mss_pub_key = _get_bcc_public_key(key_path=key_path)
    mss_pub_key.verify(
        base64.b64decode(signature),
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256(),
    )


def _get_bcc_public_key(key_path: Path):
    """Loads the public key for BCC given the path to the key file

    Args:
        key_path: the file path to the RSA public key PEM file

    Returns:
        the public key of the MSS
    """
    global _BCC_PUBLIC_KEYS
    key_path_str = str(key_path)

    if key_path_str not in _BCC_PUBLIC_KEYS:
        with open(key_path, "rb") as key_file:
            data = key_file.read()
            _BCC_PUBLIC_KEYS[key_path_str] = serialization.load_pem_public_key(data)

    return _BCC_PUBLIC_KEYS[key_path_str]


def get_request_logs_store() -> Collection[WebsocketRequestLog]:
    """Gets the store for the given url for the request logs

    Returns:
        the RedisCollection containing the jobs
    """
    global _REQUEST_LOGS_STORE
    if _REQUEST_LOGS_STORE is None:
        connection = Redis.from_url(url=f"{settings.CONFIG.database.redis_url}")
        _REQUEST_LOGS_STORE = Collection(
            connection=connection, schema=WebsocketRequestLog
        )

    return _REQUEST_LOGS_STORE
