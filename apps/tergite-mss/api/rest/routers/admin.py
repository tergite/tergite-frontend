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
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status

from services.auth import (
    APP_TOKEN_AUTH,
    Project,
    User,
    user_requests,
)
from services.external.bcc.dtos import BCCUserProfile, GeneralMessage, NewBCCUserInfo
from utils.api import PaginatedListResponse

from ..dependencies import CurrentSuperuserDep, CurrentUserDep, CurrentUserIdDep

router = APIRouter(prefix="/admin")

router.include_router(
    APP_TOKEN_AUTH.get_projects_router(),
    prefix="/projects",
    tags=["projects"],
)


@router.get(
    "/qpu-time-requests/", tags=["user-requests"], dependencies=[CurrentUserIdDep]
)
async def get_qpu_time_requests(
    project_ids: Optional[List[str]] = Query(None, alias="project_id"),
    status: Optional[user_requests.UserRequestStatus] = Query(None),
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
):
    """Retrieves the qpu time requests filtered by the given query params"""
    filters = {}
    if isinstance(project_ids, list):
        filters["request.project_id"] = {"$in": project_ids}
    if status is not None:
        filters["status"] = status
    data = await user_requests.get_many_qpu_time_requests(
        filters, skip=skip, limit=limit
    )
    return PaginatedListResponse(data=data, skip=skip, limit=limit).model_dump(
        mode="json", exclude_data_none_fields=False
    )


@router.post(
    "/qpu-time-requests/",
    tags=["user-requests"],
    status_code=http_status.HTTP_201_CREATED,
)
async def create_qpu_time_request(
    request_body: user_requests.QpuTimeExtensionPostBody,
    requester: User = CurrentUserDep,
):
    """Creates a new QPU time request"""
    project = await Project.find_one(
        {
            "_id": PydanticObjectId(request_body.project_id),
            "user_ids": str(requester.id),
        }
    )
    if project is None:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN)

    request_body.project_name = project.name
    result = await user_requests.create_qpu_time_request(
        request_body=request_body,
        requester=requester,
    )
    return result.model_dump(mode="json")


@router.get(
    "/user-requests/", tags=["user-requests"], dependencies=[CurrentSuperuserDep]
)
async def get_user_requests(
    status: Optional[user_requests.UserRequestStatus] = Query(None),
    skip: int = Query(0),
    limit: Optional[int] = Query(None),
):
    """Gets the user requests that match the given filters"""
    filters = {}
    if status is not None:
        filters["status"] = status
    data = await user_requests.get_many(filters, skip=skip, limit=limit)
    return PaginatedListResponse(data=data, skip=skip, limit=limit).model_dump(
        mode="json",
        exclude_data_none_fields=False,
    )


@router.post("/bcc-users/{backend}")
async def create_bcc_user(
    backend: str,
    data: NewBCCUserInfo,
    requester: User = CurrentUserDep,
) -> "BCCUserProfile":
    """Creates a user in the given backend for info

    Only MSS admin users can create users here

    Args:
        backend: the name of the backend
        data: the information about the new user
        requester: the admin user requesting this operation

    Returns:
        the created user
    """
    raise NotImplementedError("not implemented")


@router.delete("/bcc-users/{backend}/{user_id}")
async def remove_bcc_user(
    backend: str,
    user_id: str,
    requester: User = CurrentUserDep,
) -> GeneralMessage:
    """Deletes the user of the given user_id

    Only admins are allowed to remove users

    Args:
        backend: the name of the backend
        user_id: the unique identifier of the user
        requester: the admin user requesting this operation

    Raises:
        ItemNotFoundError: user not found

    Returns:
        A general message object with status
    """
    raise NotImplementedError("not implemented")


@router.get("/bcc-users/{backend}/")
async def view_bcc_users(
    backend: str,
    skip: int = Query(default=0),
    limit: Optional[int] = Query(default=None),
    requester: User = CurrentUserDep,
) -> PaginatedListResponse[BCCUserProfile]:
    """Views all users

    Only MSS admin users can view this

    Args:
        backend: the name of the backend
        skip: number of records to ignore at the top of the returned results; default is 0
        limit: maximum number of records to return; default is None.
        requester: the admin user requesting this operation

    Returns:
        the paginated list of the available bookings
    """
    raise NotImplementedError("not implemented")


@router.put("/user-requests/{_id}", tags=["user-requests"])
async def update_user_request(
    _id: PydanticObjectId,
    body: user_requests.UserRequestUpdate,
    user: User = CurrentSuperuserDep,
):
    """Updates the user request of the given id with the body content

    This also does any necessary operations in case this update is an approval
    """
    result = await user_requests.update(_id, payload=body, admin_user=user)
    return result.model_dump(mode="json")
