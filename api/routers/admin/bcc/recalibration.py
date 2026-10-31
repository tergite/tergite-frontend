# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Routes for BCC recalibration related operations"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from services.external.bcc import RecalibrationInfo
from utils.api import GeneralMessage

from ....dependencies import (
    BccClientDep,
    CurrentSuperuserDep,
)

router = APIRouter()


@router.post("/{backend}/init")
async def initialize_recalibration(
    bcc_client: BccClientDep,
    requester: CurrentSuperuserDep,
    start_timestamp: Optional[datetime] = Query(None),
    interval: Optional[float] = Query(None),
) -> GeneralMessage:
    """Initializes recalibration of the given backend

    Only MSS admin users can initialize recalibration

    Args:
        bcc_client: the BCC client for the given backend
        start_timestamp: the start time of the recalibration; default = None i.e. straight away
        interval: the recalibration interval; default = None i.e. no repeat
        requester: the admin user requesting this operation

    Returns:
        the status of the recalibration
    """
    response = await bcc_client.init_recalibration(
        user_id=requester.id,
        start_timestamp=start_timestamp,
        interval=interval,
        is_admin=requester.is_superuser,
    )
    return response


@router.get("/{backend}/info")
async def get_recalibration_info(
    bcc_client: BccClientDep,
    requester: CurrentSuperuserDep,
) -> RecalibrationInfo:
    """Gets the current information about the recalibration of the given backend

    Only MSS admin users can get recalibration info

    Args:
        bcc_client: the BCC client for the given backend
        requester: the admin user requesting this operation

    Returns:
        the information about the recalibration
    """
    response = await bcc_client.get_recalibration_info(
        user_id=requester.id,
        is_admin=requester.is_superuser,
    )
    return response


@router.post("/{backend}/cancel")
async def cancel_recalibration(
    bcc_client: BccClientDep,
    requester: CurrentSuperuserDep,
    ignore_errors: bool = Query(False),
) -> GeneralMessage:
    """Cancels recalibration on this device

    Only MSS admin users can cancel recalibration

    Args:
        bcc_client: the BCC client for the given backend
        ignore_errors: whether to ignore errors during recalibration
        requester: the admin user requesting this operation

    Returns:
        general information on the status of the request
    """
    response = await bcc_client.stop_recalibration(
        user_id=requester.id,
        is_admin=requester.is_superuser,
        ignore_errors=ignore_errors,
    )
    return response
