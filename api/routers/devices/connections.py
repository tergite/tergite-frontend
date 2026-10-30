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
import asyncio
from typing import Optional

from fastapi.websockets import WebSocket
from loguru import logger

from libs.storage import Database
from services import devices
from utils.crypto import get_uuid4_str


class WebsocketConnectionManager:
    """Holds the live websockets of the devices in this process, several per device, as a
    backend opens one per process, and keeps their connections in the database from lapsing
    """

    def __init__(self) -> None:
        # by websocket, the id of its connection in the database
        self.active_connections: dict[WebSocket, str] = {}
        self._refresher: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket, connection_id: str) -> None:
        """Allows a connection to be established"""
        request_id = websocket.headers.get("x-request-id")
        if request_id is None:
            request_id = get_uuid4_str()

        websocket.state.request_id = request_id

        await websocket.accept(headers=[(b"x-request-id", request_id.encode("utf8"))])
        self.active_connections[websocket] = connection_id
        logger.info("Connected: {} at {}", websocket.client.host, websocket.url)

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes a given websocket connection, if it was accepted"""
        if self.active_connections.pop(websocket, None) is not None:
            logger.info("Disconnected: {} at {}", websocket.client.host, websocket.url)

    def start_refreshing(self, database: Database) -> None:
        """Refreshes the connections of this process's websockets every
        CONNECTION_REFRESH_SECONDS, and with them every device's online flag, so that those
        of a process that died lapse, and a missed change is put right"""
        self._refresher = asyncio.create_task(
            self._keep_connections_live_forever(database)
        )

    async def close_all(self, reason: str = "Server closing connection") -> None:
        """Stops refreshing, and closes all active connections

        Args:
            reason: Reason for closing the connection
        """
        if self._refresher is not None:
            self._refresher.cancel()
        for connection in list(self.active_connections):
            logger.info("Closing: {} at {}", connection.client.host, connection.url)
            await connection.close(code=1001, reason=reason)

    async def _keep_connections_live_forever(self, database: Database) -> None:
        while True:
            await asyncio.sleep(devices.CONNECTION_REFRESH_SECONDS)
            try:
                await devices.keep_connections_live(
                    database, list(self.active_connections.values())
                )
                await devices.sync_online_flags(database)
            except Exception:
                logger.exception("refreshing the devices' connections failed")
