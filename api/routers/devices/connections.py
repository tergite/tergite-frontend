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
from fastapi.websockets import WebSocket
from loguru import logger

from utils.crypto import get_uuid4_str


class WebsocketConnectionManager:
    """Holds the live websockets of the devices"""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Allows a connection to be established"""
        request_id = websocket.headers.get("x-request-id")
        if request_id is None:
            request_id = get_uuid4_str()

        websocket.state.request_id = request_id

        await websocket.accept(headers=[(b"x-request-id", request_id.encode("utf8"))])
        self.active_connections.append(websocket)
        logger.info("Connected: {} at {}", websocket.client.host, websocket.url)

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes a given websocket connection"""
        self.active_connections.remove(websocket)
        logger.info("Disconnected: {} at {}", websocket.client.host, websocket.url)

    async def close_all(self, reason: str = "Server closing connection") -> None:
        """Closes all active connections

        Args:
            reason: Reason for closing the connection
        """
        for connection in list(self.active_connections):
            logger.info("Closing: {} at {}", connection.client.host, connection.url)
            await connection.close(code=1001, reason=reason)
