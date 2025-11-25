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

from fastapi import APIRouter, Depends, Query
from fastapi.websockets import WebSocket
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from api.rest.dependencies import CurrentSystemUserProjectDep, MongoDbDep
from api.rest.utils import WebsocketConnectionManager
from services import devices, calibration as calibration_service
from services.calibration import DeviceCalibrationCreate
from services.devices import DeviceUpsert
from services.devices.dtos import DeviceQuery, DeviceStatusMessage, DeviceStatus
from utils.api import PaginatedListResponse

router = APIRouter(prefix="/devices", tags=["devices"])
ws_manager = WebsocketConnectionManager()


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


# TODO: Add certificate based security
#   - should MSS send a token to the backends that it expects?
#       - Say backend makes request to an unauthenticated endpoint requesting to be sent a very short-lived JWT token
#           MSS makes a separate request to the backend it registered
#           then backend creates a websocket connection to MSS using the token and keeps send it data
#   - should MSS have the public certificates of all the backends it connects to and
#       use those to verify that the connection is coming from right backend;
#       - maybe have the initial data encrypted with MSS public key and MSS decrypts it first with its key
#         then with the backend's public key
@router.websocket("/ws/{name}")
async def update_device_status(websocket: WebSocket, name: str, db: MongoDbDep):
    """Receives updates about the given device

    Args:
        websocket: the websocket instance
        name: the name of the device
        db: the mongo db instance
    """
    await devices.connect_device(db, name=name)
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            try:
                parsed_data = await DeviceStatusMessage.model_validate(data)
                if parsed_data.status == DeviceStatus.INITIALIZED:
                    await devices.upsert_device(db, payload=parsed_data.data)

                elif parsed_data.status == DeviceStatus.RECALIBRATED:
                    await calibration_service.insert_one(db, parsed_data.data)

                await ws_manager.reply(
                    websocket,
                    {
                        "status": "success",
                        "detail": f"status '{parsed_data.status}' registered",
                    },
                )
            except ValidationError:
                await ws_manager.reply(
                    websocket, {"status": "error", "detail": "invalid data"}
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        await devices.disconnect_device(db, name=name)
