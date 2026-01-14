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
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, WebSocketException
from fastapi.websockets import WebSocket
from pydantic import ValidationError
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.websockets import WebSocketDisconnect

from api.rest.dependencies import MongoDbDep, ProjectDbDep
from api.rest.utils import get_verified_device_name
from services import devices
from services.devices.dtos import (
    DeviceEvent,
    DeviceEventHandler,
    DeviceEventName,
    DeviceQuery,
)
from utils.api import PaginatedListResponse, WebsocketConnectionManager

from .events import (
    on_device_initialized_event,
    on_device_recalibrated_event,
    on_job_updated_event,
)

router = APIRouter(prefix="/devices", tags=["devices"])
ws_manager = WebsocketConnectionManager()
_EVENT_HANDLER_MAP: Dict[DeviceEventName, DeviceEventHandler] = {
    DeviceEventName.INITIALIZED: on_device_initialized_event,
    DeviceEventName.RECALIBRATED: on_device_recalibrated_event,
    DeviceEventName.JOB_UPDATED: on_job_updated_event,
}
"""A map of event handlers for device events"""


@router.get("/")
async def read_many(
    db: MongoDbDep,
    query: DeviceQuery = Depends(),
    skip: int = 0,
    limit: Optional[int] = None,
    sort: List[str] = Query(("-created_at",)),
):
    """Gets a paginated list of devices that fulfill a given set of filters

    Args:
        db: the mongo db database from which to get the device data
        query: the query params for getting the device data
        skip: the number of records to skip
        limit: the maximum number of records to return
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ("-created_at",)
            To add multiple fields to sort by, repeat the same query parameter in the url e.g. "query=tom&q=dick&q=harry"

    Returns:
        the paginated result of the matched device data
    """
    filters = query.model_dump()

    data = await devices.get_all_devices(
        db, filters=filters, skip=skip, limit=limit, sort=sort
    )

    return PaginatedListResponse(skip=skip, limit=limit, data=data).model_dump(
        mode="json", exclude_data_none_fields=False
    )


@router.get("/{name}")
async def read_one(db: MongoDbDep, name: str):
    record = await devices.get_one_device(db, name=name)
    return record.model_dump(mode="json")


@router.websocket("/ws/{name}")
async def handle_device_events(
    websocket: WebSocket,
    name: str,
    db: MongoDbDep,
    project_db: ProjectDbDep,
    verified_name: str = Depends(get_verified_device_name),
):
    """Receives updates about the given device

    Args:
        websocket: the websocket instance
        name: the name of the device
        db: the mongo db instance
        project_db: the database containing the project
        verified_name: the verified name of the device
    """
    if verified_name != name:
        raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="forbidden")

    await devices.try_connect_device(db, name=name)
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            try:
                parsed_data = DeviceEvent.model_validate(data)
                handler = _EVENT_HANDLER_MAP[parsed_data.name]
                response = await handler(
                    device=verified_name,
                    data=parsed_data.data,
                    db=db,
                    project_db=project_db,
                )

            except ValidationError as exp:
                response = {"status": "error", "detail": f"invalid data: {exp}"}
            except PermissionError as exp:
                response = {"status": "error", "detail": f"forbidden: {exp}"}
            except Exception as exp:
                logging.error(exp)
                response = {"status": "error", "detail": f"unexpected server error"}

            await ws_manager.reply(websocket, response)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        await devices.try_disconnect_device(db, name=name)
