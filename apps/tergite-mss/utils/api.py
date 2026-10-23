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
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Literal,
    NotRequired,
    Optional,
    Sequence,
    TypedDict,
    TypeVar,
)

from fastapi import WebSocketException, status
from fastapi.websockets import WebSocket
from loguru import logger
from pydantic import BaseModel

from utils.crypto import get_uuid4_str

ITEM = TypeVar("ITEM", bound=BaseModel)


class PaginatedListResponse(BaseModel, Generic[ITEM]):
    """The response when sending paginated data"""

    skip: int = 0
    limit: Optional[int] = None
    data: List[ITEM] = []


def get_paginated_json(
    data: Sequence[BaseModel],
    skip: int,
    limit: Optional[int],
    should_exclude_none: bool = True,
) -> Dict[str, Any]:
    """Builds the JSON body of a paginated list, shaped as PaginatedListResponse

    Args:
        data: the items on this page
        skip: the number of items skipped
        limit: the maximum number of items asked for
        should_exclude_none: whether to drop the items' fields that are None

    Returns:
        the JSON-able dict of the list
    """
    return {
        "skip": skip,
        "limit": limit,
        "data": [
            item.model_dump(mode="json", exclude_none=should_exclude_none)
            for item in data
        ],
    }


class GeneralMessage(TypedDict):
    """A general message object sent on the API"""

    status: Literal["success", "error", "cancelled", "failed"]
    detail: NotRequired[str]
    data: NotRequired[dict | list]


class CountsResponse(TypedDict):
    """The response when a counts API endpoint is hit"""

    count: int


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

        await websocket.accept(headers=[(b"x-request-id", request_id.encode("utf8"))])
        self.active_connections.append(websocket)
        logger.info("Connected: {} at {}", websocket.client.host, websocket.url)

    def disconnect(self, websocket: WebSocket):
        """Removes a given websocket connection"""
        self.active_connections.remove(websocket)
        logger.info("Disconnected: {} at {}", websocket.client.host, websocket.url)

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
            logger.info("Closing: {} at {}", connection.client.host, connection.url)
            await connection.close(code=1001, reason=reason)


async def get_websocket_json(
    websocket: WebSocket, data_type: Literal["text", "binary"]
) -> dict:
    """Gets the JSON data in the given websocket

    Args:
        websocket: the websocket object
        data_type: the type of the data to expect to come from the websocket

    Raises:
        fastapi.WebSocketException: invalid data type: websocket only supports {data_type} data
    """
    try:
        return await websocket.receive_json(mode=data_type)
    except KeyError:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=f"invalid data type: websocket only supports {data_type} data",
        )
