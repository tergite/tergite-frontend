# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Routes for admin related operations"""

from fastapi import APIRouter

from utils.api import GeneralMessage

from ....dependencies import (
    BccClientDep,
    CurrentSuperuserDep,
    RequestIdDep,
)

router = APIRouter()


@router.post("/{backend}/off")
async def switch_backend_off(
    bcc_client: BccClientDep,
    request_id: RequestIdDep,
    requester: CurrentSuperuserDep,
) -> GeneralMessage:
    """Switches off the backend

    Only MSS admin users can switch off the device

    Args:
        bcc_client: the BCC client for the given backend
        request_id: the unique identifier of the request
        requester: the admin user requesting this operation

    Returns:
        general information on the status of the request
    """
    response = await bcc_client.switch_off(
        user_id=requester.id,
        request_id=request_id,
        is_admin=requester.is_superuser,
    )
    return response


@router.post("/{backend}/on")
async def switch_backend_on(
    bcc_client: BccClientDep,
    request_id: RequestIdDep,
    requester: CurrentSuperuserDep,
) -> GeneralMessage:
    """Switches on the backend

    Only MSS admin users can switch off the device

    Args:
        bcc_client: the BCC client for the given backend
        request_id: the unique identifier of the request
        requester: the admin user requesting this operation

    Returns:
        general information on the status of the request
    """
    response = await bcc_client.switch_on(
        user_id=requester.id,
        request_id=request_id,
        is_admin=requester.is_superuser,
    )
    return response
