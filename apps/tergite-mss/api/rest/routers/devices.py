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
from datetime import datetime
from typing import List, Optional

from cryptography.exceptions import InvalidSignature
from fastapi import APIRouter, Depends, Query, WebSocketException
from fastapi.websockets import WebSocket
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError, BaseModel
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.websockets import WebSocketDisconnect

import settings
from api.rest.dependencies import CurrentSystemUserProjectDep, MongoDbDep
from api.rest.utils import WebsocketConnectionManager
from services import devices, calibration as calibration_service
from services.calibration import DeviceCalibrationCreate
from services.devices import DeviceUpsert
from services.devices.dtos import DeviceQuery, DeviceStatusMessage, DeviceStatus
from utils.api import PaginatedListResponse, verify_bcc_signature

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

class BCCTokenClaims(BaseModel):
    """The model of the claims stored in special BCC JWT token"""
    name: str

def get_verified_device_name(websocket: WebSocket) -> str:
    """Returns the device name as got from BCC passed through special headers

    We are choosing to trust BCC and so whenever a request comes from
    BCC, there will be an `x-bcc-name` and `x-bcc-signature` header.
    We will get the `x-bcc-name` and return it only if the `x-bcc-signature`
    is verified by BCC public key and the client host is what is expected by MSS.

    For better security against replay attacks, we also use the `x-bcc-request-id` and
    `x-bcc-timestamp` headers

    Args:
        websocket: the current FastAPI request

    Returns:
        the name of the device

    Raises:
        NotAuthenticatedError: user not authenticated
    """
    try:
        name = websocket.headers["x-bcc-name"]
        nonce = websocket.headers["x-bcc-request-id"]
        timestamp = websocket.headers["x-bcc-timestamp"]
        signature = websocket.headers["x-bcc-signature"]

        if websocket.client.host != settings.CONFIG.backends_dict[name].url.host:
            raise ValueError(f"unexpected origin {websocket.client.host}")

        message = f"{name}-{nonce}-{timestamp}"
        verify_bcc_signature(signature=signature, message=message, key_path=settings.CONFIG.backends_dict[name].public_key_path)

        current_timestamp = datetime.now().timestamp()
        timestamp_float = float(timestamp)
        time_difference = current_timestamp - timestamp_float
        if time_difference > settings.CONFIG.bcc_nonce_ttl:
            raise ValueError(
                f"nonce of timestamp {timestamp} is {time_difference}s older than {settings.CONFIG.bcc_nonce_ttl} seconds"
            )
        elif time_difference < 0:
            raise ValueError(f"timestamp {timestamp} is in the future")

        requests_store = get_request_logs_store()
        if requests_store.exists(nonce):
            raise ValueError(f"duplicate request nonce: '{nonce}'")

        return name
    except (KeyError, InvalidSignature, ValueError, AttributeError) as exp:
        logging.error(exp)
        raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="unauthorized")


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
async def update_device_status(websocket: WebSocket, name: str, db: MongoDbDep, verified_name: str = Depends(get_verified_device_name)):
    """Receives updates about the given device

    Args:
        websocket: the websocket instance
        name: the name of the device
        db: the mongo db instance
        verified_name: the verified name of the device
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
