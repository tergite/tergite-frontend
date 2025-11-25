# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Some utility functions for the routers"""
import uuid

from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import Message, Send
from fastapi.websockets import WebSocket

from utils.api import GeneralMessage
from utils.exc import InvalidRequestIDError
from utils.logging import access_logger


class TergiteCORSMiddleware(CORSMiddleware):
    """Custom CORS middleware to handle Tergite specific behaviour"""

    async def send(
        self, message: Message, send: Send, request_headers: Headers
    ) -> None:
        if message["type"] != "http.response.start":
            await send(message)
            return

        message.setdefault("headers", [])
        headers = MutableHeaders(scope=message)
        headers.update(self.simple_headers)
        origin = request_headers["Origin"]

        # If all origins are allowed, respond back with the Origin header
        if self.allow_all_origins:
            self.allow_explicit_origin(headers, origin)

        # If we only allow specific origins, then we have to mirror back
        # the Origin header in the response.
        elif not self.allow_all_origins and self.is_allowed_origin(origin=origin):
            self.allow_explicit_origin(headers, origin)

        await send(message)


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


class WebsocketConnectionManager:
    """Manages connections to a websockets endpoint"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Allows a connection to be established"""
        await websocket.accept()
        self.active_connections.append(websocket)
        access_logger.info(f"Connected: {websocket.client.host} at {websocket.url}")

    def disconnect(self, websocket: WebSocket):
        """Removes a given websocket connection"""
        self.active_connections.remove(websocket)
        access_logger.info(f"Disconnected: {websocket.client.host} at {websocket.url}")

    async def reply(self, websocket: WebSocket, message: GeneralMessage):
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
            access_logger.info(f"Closing: {connection.client.host} at {connection.url}")
            await connection.close(code=1001, reason=reason)


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
