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
import asyncio
from typing import Any, Dict, List, Optional, Sequence, Tuple

import motor.motor_asyncio
from beanie import PydanticObjectId, SortDirection
from beanie.odm.operators.find.comparison import In
from beanie.odm.operators.update.array import AddToSet
from beanie.odm.operators.update.general import Set
from pymongo.errors import DuplicateKeyError

from services import notices
from services.auth.app_tokens.database import AppTokenDatabase
from services.auth.projects import get_project_db
from services.auth.projects.dtos import Project
from services.auth.projects.manager import ProjectAppTokenManager
from services.auth.users.database import UserDatabase
from services.auth.users.dtos import User
from services.notices.dtos import RefType
from utils.config import UserRole
from utils.exc import ConflictError, ForbiddenError, NotFoundError
from utils.mongodb import init_strict_beanie

from .dtos import (
    CreateProjectMetadata,
    Request,
    RequestPostBody,
    RequestStatus,
    RequestTarget,
    RequestType,
    RequestUpdate,
)

_DECIDED_STATUSES = (RequestStatus.APPROVED, RequestStatus.REJECTED)
ALL_REQ_TYPES = tuple(RequestType)
ALL_REQ_STATUSES = tuple(RequestStatus)


async def on_startup(db: motor.motor_asyncio.AsyncIOMotorDatabase):
    """Runs init operations when the application is starting up"""
    await init_strict_beanie(
        database=db,
        document_models=[
            Request,
        ],
    )


async def create(
    request_body: RequestPostBody,
    requester: User,
) -> Request:
    """Creates a new user request given the request body, requester_id and request type

    Args:
        request_body: the POST body of the request
        requester: the user making the request

    Returns:
        the created Request object

    Raises:
        NotFoundError: project {id} not found
        ForbiddenError: if the user does not have permission to perform the request
        ConflictError: if the request is redundant
    """
    project = await _get_project(request_body)
    if not _has_resource_access(request_body, user=requester, project=project):
        raise ForbiddenError(
            f"operation not permitted on resource {request_body.resource_id}"
        )

    await _raise_if_redundant(request_body, requester=requester, project=project)
    target_user_ids = await _get_target_user_ids(request_body, project=project)
    record = Request.from_post_body(
        request_body, requester=requester, target_user_ids=target_user_ids
    )
    if project is not None:
        record.metadata.project_name = project.name

    await record.create()
    # NOTE: We explicitly notify here instead of in a beanie hook because:
    #   - hooks would have hidden the logic to a reader/maintainer in future
    await notices.create_system_notice(
        user_ids=target_user_ids,
        notice_type=record.notice_type.id,
        ref_id=record.id,
        ref_type=RefType.USER_REQUEST,
        context=record.notice_context,
    )
    return record


async def get_one(pk: PydanticObjectId, current_user_id: PydanticObjectId) -> Request:
    """Gets a single request if the given user is allowed to see it

    Args:
        pk: the id of the request
        current_user_id: the identifier of the current user

    Returns:
        the Request object

    Raises:
        NotFoundError if the request is not found
    """
    record = await Request.find_one(
        {
            "_id": pk,
            "$or": [
                {"target_user_ids": current_user_id},
                {"requester_id": current_user_id},
            ],
        }
    )
    if record is None:
        raise NotFoundError(f"{pk} not found")
    return record


async def get_many(
    filter_obj: Dict[str, Any],
    current_user_id: PydanticObjectId,
    request_types: Tuple[RequestType, ...] = ALL_REQ_TYPES,
    sort: tuple[str, ...] = ("-created_at",),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Request]:
    """Gets multiple requests that match the given filter and request types and can be viewed by current user

    Requesters and target users of a given request can view it

    Args:
        filter_obj: the PyMongo-like filter object e.g. `{"approver_id": "some-guys-id"}`.
        current_user_id: the identifier of the current user
        request_types: the types of request to return. default = ALL_REQ_TYPES
        sort: the sort order of the returned results
        skip: the number of matched records to skip
        limit: the maximum number of records to return.
                If None, all possible records are returned.

    Returns:
        the list of request objects
    """
    _filter = {
        **filter_obj,
        "type": {"$in": request_types},
        "$or": [
            {"target_user_ids": current_user_id},
            {"requester_id": current_user_id},
        ],
    }
    sort_args = _to_sort_pairs(sort)
    return await Request.find(
        _filter,
        skip=skip,
        limit=limit,
        sort=sort_args,
    ).to_list()


async def update(
    filter_obj: Dict[str, Any],
    payload: RequestUpdate,
    current_user: User,
    sort: tuple[str, ...] = ("-created_at",),
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Request]:
    """Updates the matched requests.

    Note: only approvers can update a request that has been made.
    Requesters can delete and create another.
    The reasoning is updating it would require we send a new notice
    and the approver might get confused about which is which.

    Note: We don't change the status of finalized requests
    for the same reason of the potential of misalignment. Better
    to make a new request.

    Approval side effects are applied before the requests are marked decided, so that a
    failure leaves a retryable pending request rather than an approved request with
    nothing done.

    Args:
        filter_obj: the filters to match
        payload: the update payload for the requests
        current_user: the logged-in user
        sort: the sort order of the returned results
        skip: the number of matched records to skip
        limit: the maximum number of records to match.
                If None, all possible records are matched.

    Returns:
        Returns all updated requests

    Raises:
        NotFoundError: no match found
    """
    _filter = {} if filter_obj is None else {**filter_obj}
    # only requests that are pending can be updated
    # only requests that a user is a target can be updated
    _filter.update(
        {"target_user_ids": current_user.id, "status": RequestStatus.PENDING}
    )
    sort_args = _to_sort_pairs(sort)
    matches = await Request.find(
        _filter, skip=skip, limit=limit, sort=sort_args
    ).to_list()
    if len(matches) == 0:
        raise NotFoundError("no match found")

    if payload.status == RequestStatus.APPROVED:
        for item in matches:
            await _apply_approval(item)

    # add approver_id, approver_name to the update
    update_dict = payload.model_dump(exclude_unset=True)
    update_dict.update(
        {
            "approver_id": current_user.id,
            "approver_name": current_user.username,
        }
    )
    ids = [item.id for item in matches]
    await Request.find(In(Request.id, ids)).update({"$set": update_dict})
    result = await Request.find(In(Request.id, ids), sort=sort_args).to_list()

    if payload.status in _DECIDED_STATUSES:
        await notices.clear_notices_by_reference({RefType.USER_REQUEST: ids})
        await asyncio.gather(
            *(
                notices.create_system_notice(
                    user_ids=(item.requester_id,),
                    notice_type=item.notice_type.id,
                    ref_id=item.id,
                    ref_type=RefType.USER_REQUEST,
                    context=item.notice_context,
                )
                for item in result
            )
        )
    return result


def _to_sort_pairs(sort_fields: Sequence[str]) -> List[Tuple[str, SortDirection]]:
    """Converts a list of sort fields with '-' prepended for descending to tuples of field and direction.

    Args:
        sort_fields: the sort fields

    Returns:
        the tuples of the fields with their directions of sorting
    """
    sort_args = []
    for field in sort_fields:
        cleaned_field = field.lstrip("-")
        direction = (
            SortDirection.DESCENDING
            if field.startswith("-")
            else SortDirection.ASCENDING
        )
        sort_args.append((cleaned_field, direction))

    return sort_args


async def _get_project(request: RequestPostBody) -> Optional[Project]:
    """Gets the project that the given request is about

    Args:
        request: the request post body

    Returns:
        the project or None if the request is to create one

    Raises:
        NotFoundError: project {id} not found
    """
    if request.type == RequestType.CREATE_PROJECT:
        return None

    project = await Project.get(request.resource_id)
    # FIXME: Restored from before the requests were unified: personal projects answer
    #   404 identically to missing ones, so they cannot be probed for access.
    is_hidden = project is not None and project.is_personal
    if project is None or (request.type == RequestType.PROJECT_ACCESS and is_hidden):
        raise NotFoundError(f"project {request.resource_id} not found")

    return project


async def _get_target_user_ids(
    request: RequestPostBody, project: Optional[Project]
) -> List[PydanticObjectId]:
    """Gets the IDs of users to whom this request is directed

    Args:
        request: the request post body
        project: the project the request is about, if any

    Returns:
        the IDs of the target users
    """
    if request.target == RequestTarget.PROJECT:
        return [project.admin_id]

    elif request.target == RequestTarget.SYSTEM:
        superusers = await User.find({"roles": UserRole.ADMIN}).to_list()
        return [user.id for user in superusers]

    return []


def _has_resource_access(
    request: RequestPostBody, user: User, project: Optional[Project]
) -> bool:
    """Checks if the user has access to the resource they are requesting on

    Args:
        request: the request post body
        user: the user to check
        project: the project the request is about, if any

    Returns:
        True if the user has access to the resource
    """
    if request.type in (RequestType.CREATE_PROJECT, RequestType.PROJECT_ACCESS):
        return user is not None

    elif request.type in (RequestType.CLOSE_PROJECT, RequestType.TRANSFER_PROJECT):
        return project.admin_id == user.id

    elif request.type == RequestType.PROJECT_QPU_SECONDS:
        return user.id in project.members

    return False


async def _raise_if_redundant(
    request: RequestPostBody, requester: User, project: Optional[Project]
):
    """Raises an error if the given request would change nothing

    FIXME: Restored from before the requests were unified. Reconsider these guards
      when refactoring the requests to match the rest of the code base.

    Args:
        request: the request post body
        requester: the user making the request
        project: the project the request is about, if any

    Raises:
        ConflictError: you are already a member of '{project_name}'
        ConflictError: a request for '{name}' is already pending
    """
    if request.type == RequestType.PROJECT_ACCESS and requester.id in project.members:
        raise ConflictError(f"you are already a member of '{project.name}'")

    pending_duplicate = await Request.find_one(
        {
            "type": request.type,
            "resource_id": request.resource_id,
            "requester_id": requester.id,
            "status": RequestStatus.PENDING,
        }
    )
    if pending_duplicate is not None:
        name = project.name if project else request.metadata.name
        raise ConflictError(f"a request for '{name}' is already pending")


# FIXME: Restored from before the requests were unified, so that approving a request
#   does what was asked for. Reconsider where these side effects belong, e.g. with the
#   projects service, when refactoring the requests to match the rest of the code base.
async def _apply_approval(request: Request):
    """Does what the given request asks for, as it is being approved

    Args:
        request: the request being approved

    Raises:
        NotFoundError: project {id} not found
        NotFoundError: no users of emails {emails}
        ConflictError: a project named '{name}' already exists
    """
    metadata = request.metadata
    project_id = request.resource_id

    if request.type == RequestType.CREATE_PROJECT:
        await _create_requested_project(metadata)
        return

    project = await Project.get(project_id)
    if project is None:
        raise NotFoundError(f"project {project_id} not found")

    if request.type == RequestType.PROJECT_ACCESS:
        await Project.find_one(Project.id == project_id).update(
            AddToSet({Project.user_ids: request.requester_id})
        )

    elif request.type == RequestType.PROJECT_QPU_SECONDS:
        project_db = await get_project_db()
        await project_db.increment_qpu_seconds(project_id, metadata.seconds)

    elif request.type == RequestType.TRANSFER_PROJECT:
        email_id_map = await _get_user_email_id_map([metadata.admin_email])
        new_admin_id = email_id_map[metadata.admin_email]
        await Project.find_one(Project.id == project_id).update(
            Set({Project.admin_id: new_admin_id}),
            AddToSet({Project.user_ids: new_admin_id}),
        )

    elif request.type == RequestType.CLOSE_PROJECT:
        project_manager = ProjectAppTokenManager(
            await get_project_db(),
            app_token_db=AppTokenDatabase(),
            user_db=UserDatabase(),
        )
        await project_manager.delete(project, is_superuser=True)


async def _create_requested_project(metadata: CreateProjectMetadata):
    """Creates the project described in the metadata of a create-project request

    Args:
        metadata: the metadata of the create-project request

    Raises:
        NotFoundError: no users of emails {emails}
        ConflictError: a project named '{name}' already exists
    """
    email_id_map = await _get_user_email_id_map(
        [metadata.admin_email, *metadata.user_emails]
    )
    admin_id = email_id_map[metadata.admin_email]
    user_ids = [email_id_map[email] for email in metadata.user_emails]
    project = Project(
        name=metadata.name,
        description=metadata.description,
        qpu_seconds=metadata.qpu_seconds,
        admin_id=admin_id,
        user_ids=list(dict.fromkeys([*user_ids, admin_id])),
    )

    try:
        await project.create()
    except DuplicateKeyError:
        raise ConflictError(f"a project named '{metadata.name}' already exists")


async def _get_user_email_id_map(
    emails: Sequence[str],
) -> Dict[str, PydanticObjectId]:
    """Gets the IDs of the users of the given emails, keyed by email

    Args:
        emails: the emails of the users

    Returns:
        the map of email to user ID

    Raises:
        NotFoundError: no users of emails {emails}
    """
    users = await User.find(In(User.email, list(emails))).to_list()
    email_id_map = {user.email: user.id for user in users}
    missing_emails = [email for email in emails if email not in email_id_map]
    if missing_emails:
        raise NotFoundError(f"no users of emails {missing_emails}")

    return email_id_map
