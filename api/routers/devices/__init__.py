# This code is part of Tergite
#
# (C) Copyright Simon Genne, Arvid Holmqvist, Bashar Oumari, Jakob Ristner,
#               Björn Rosengren, and Jakob Wik 2022 (BSc project)
# (C) Copyright Abdullah-Al Amin 2022
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
#
# Refactored by Martin Ahindura - 2023-11-08, 2024-08-01
from typing import List, Optional

import anyio
from fastapi import APIRouter, Depends, Query, WebSocketException
from fastapi.websockets import WebSocket
from loguru import logger
from pydantic import ValidationError
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.websockets import WebSocketDisconnect

from api.dependencies import DatabaseDep
from api.utils import get_verified_device_name
from libs.storage import Database
from services import devices
from services.devices import Device, DeviceEvent, DeviceQuery
from utils.api import (
    EventResponse,
    PaginatedListResponse,
    get_paginated_json,
    get_websocket_json,
)
from utils.exc import ForbiddenError

from .connections import WebsocketConnectionManager

router = APIRouter(prefix="/devices", tags=["devices"])
ws_manager = WebsocketConnectionManager()


@router.get("/", responses={200: {"model": PaginatedListResponse[Device]}})
async def read_many(
    database: DatabaseDep,
    query: DeviceQuery = Depends(),
    skip: int = 0,
    limit: Optional[int] = None,
    sort: List[str] = Query(("-created_at",)),
):
    """Gets a paginated list of devices that fulfill a given set of filters

    Args:
        database: the database where the devices are stored
        query: the query params for getting the device data
        skip: the number of records to skip
        limit: the maximum number of records to return
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ("-created_at",)
            To add multiple fields to sort by, repeat the same query parameter in the url e.g. "query=tom&q=dick&q=harry"

    Returns:
        the paginated result of the matched device data
    """
    data = await devices.find_devices(
        database,
        query=query,
        sort=sort,
        skip=skip,
        limit=limit,
    )

    return get_paginated_json(data, skip=skip, limit=limit)


@router.get("/{name}", responses={200: {"model": Device}})
async def read_one(database: DatabaseDep, name: str):
    record = await devices.get_device(database, name=name)
    return record.model_dump(mode="json", exclude_none=True)


@router.websocket("/ws/{name}")
async def handle_device_events(
    websocket: WebSocket,
    name: str,
    database: DatabaseDep,
    verified_name: str = Depends(get_verified_device_name),
):
    """Receives updates about the given device

    Args:
        websocket: the websocket instance
        name: the name of the device
        database: the database holding the devices, calibrations, jobs and projects
        verified_name: the verified name of the device
    """
    if verified_name != name:
        raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="forbidden")

    # a device not yet registered registers itself with its 'initialized' event, which
    # the connection then marks online
    connection_id = await devices.add_connection(database, device_name=name)
    try:
        await ws_manager.connect(websocket, connection_id=connection_id)
        while True:
            data = await get_websocket_json(websocket, data_type="text")
            response = await _handle_frame(
                data,
                device=verified_name,
                database=database,
            )
            await websocket.send_json(response)

    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket)
        # shielded, so that a socket cancelled rather than closed, as the server stops, is
        # still forgotten; else it lapses
        with anyio.CancelScope(shield=True):
            await devices.remove_connection(database, connection_id)


async def _handle_frame(
    data: dict,
    device: str,
    database: Database,
) -> EventResponse:
    """Runs the handler of the event in one frame; an error becomes an error reply"""
    response: EventResponse = {"id": "unknown", "status": "success"}
    try:
        event = DeviceEvent.model_validate(data)
        response.update(id=event.id)
        handler = devices.EVENT_HANDLERS[event.name]
        response.update(
            await handler(
                device=device,
                data=event.data,
                database=database,
            )
        )
    except ValidationError as exp:
        response.update({"status": "error", "detail": f"invalid data: {exp}"})
    except ForbiddenError as exp:
        response.update({"status": "error", "detail": f"forbidden: {exp}"})
    except Exception:
        logger.exception("Unexpected exception in device websocket handler")
        response.update({"status": "error", "detail": "unexpected server error"})

    return response
