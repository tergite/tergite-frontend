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
from contextlib import suppress
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, WebSocketException
from fastapi.websockets import WebSocket
from loguru import logger
from pydantic import ValidationError
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.websockets import WebSocketDisconnect

from api.rest.dependencies import DatabaseDep, ProjectDbDep
from api.rest.utils import get_verified_device_name
from libs.storage import Database, Page, parse_sort
from services import devices
from services.auth import ProjectDatabase
from services.devices import Device, DeviceEvent, DeviceQuery
from utils.api import (
    EventResponse,
    PaginatedListResponse,
    WebsocketConnectionManager,
    build_paginated_json,
    get_websocket_json,
)
from utils.date_time import get_current_timestamp
from utils.exc import ForbiddenError, NotFoundError

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
        where=devices.build_filter(query),
        sort=parse_sort(sort),
        page=Page(skip=skip, limit=limit),
    )

    return build_paginated_json(data, skip=skip, limit=limit, should_exclude_none=False)


@router.get("/{name}", responses={200: {"model": Device}})
async def read_one(database: DatabaseDep, name: str):
    record = await devices.get_device(database, name=name)
    return record.model_dump(mode="json")


@router.websocket("/ws/{name}")
async def handle_device_events(
    websocket: WebSocket,
    name: str,
    database: DatabaseDep,
    project_db: ProjectDbDep,
    verified_name: str = Depends(get_verified_device_name),
):
    """Receives updates about the given device

    Args:
        websocket: the websocket instance
        name: the name of the device
        database: the database holding the devices, calibrations and jobs
        project_db: the database containing the project
        verified_name: the verified name of the device
    """
    if verified_name != name:
        raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="forbidden")

    # a device not yet registered registers itself with its 'initialized' event
    with suppress(NotFoundError):
        await devices.mark_device_online(database, name=name)
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await get_websocket_json(websocket, data_type="text")
            response = await _handle_frame(
                data,
                device=verified_name,
                database=database,
                project_db=project_db,
            )
            await ws_manager.reply(websocket, response)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        with suppress(NotFoundError):
            await devices.mark_device_offline(
                database, name=name, last_online=get_current_timestamp()
            )


async def _handle_frame(
    data: dict,
    device: str,
    database: Database,
    project_db: ProjectDatabase,
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
                project_db=project_db,
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
