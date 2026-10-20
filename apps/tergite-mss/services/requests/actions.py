# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""The actions that approving each type of request does"""
import asyncio
from typing import Any, Callable, Coroutine, Dict, List, Sequence, cast

from beanie import PydanticObjectId
from beanie.odm.operators.find.comparison import In
from beanie.odm.operators.update.array import AddToSet
from beanie.odm.operators.update.general import Set

from services.auth.app_tokens.database import AppTokenDatabase
from services.auth.projects import get_project_db
from services.auth.projects.dtos import Project
from services.auth.projects.exc import ProjectExists
from services.auth.projects.manager import ProjectAppTokenManager
from services.auth.projects.routers import handlers as project_handlers
from services.auth.users.database import UserDatabase
from services.auth.users.dtos import User
from utils.exc import ConflictError, NotFoundError

from .dtos import (
    CreateProjectMetadata,
    ProjectQpuSecondsMetadata,
    Request,
    RequestType,
    TransferProjectMetadata,
)

type Action = Callable[[Request, User], Coroutine[Any, Any, None]]
"""An action that approving a request does, given the request and its approver"""


async def do_many_actions(requests: List[Request], approver: User) -> None:
    """Does the actions of multiple requests, each according to its type

    Args:
        requests: The requests to do that are to be acted on
        approver: The user who is supposed to approve the request

    Raises:
        ExceptionGroup: errors doing bulk actions
            ValueError: no action for request type {type}
            NotFoundError: project {id} not found
            NotFoundError: no users of emails {emails}
            ConflictError: a project named '{name}' already exists
    """
    tasks = [_do_action(req, approver) for req in requests]

    resp = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [item for item in resp if isinstance(item, Exception)]

    if errors:
        raise ExceptionGroup("errors doing bulk action", errors)


async def _do_action(request: Request, approver: User) -> None:
    """Does what the given request asks for, as it is being approved

    Args:
        request: the request being approved
        approver: the user approving the request

    Raises:
        ValueError: no action for request type {type}
        NotFoundError: project {id} not found
        NotFoundError: no users of emails {emails}
        ConflictError: a project named '{name}' already exists
    """
    action_map: Dict[RequestType, Action] = {
        RequestType.CREATE_PROJECT: _create_project,
        RequestType.CLOSE_PROJECT: _close_project,
        RequestType.TRANSFER_PROJECT: _transfer_project,
        RequestType.PROJECT_QPU_SECONDS: _add_qpu_seconds,
        RequestType.PROJECT_ACCESS: _add_project_member,
    }

    try:
        action = action_map[request.type]
    except KeyError:
        raise ValueError(f"no action for request type {request.type}")

    await action(request, approver)


async def _create_project(request: Request, approver: User) -> None:
    """Creates the project described in the metadata of a create-project request

    Users of any emails that do not exist yet are created, as when a superuser
    creates the project directly.

    Args:
        request: the create-project request
        approver: the user approving the request

    Raises:
        ConflictError: a project named '{name}' already exists
    """
    metadata = cast(CreateProjectMetadata, request.metadata)
    try:
        await project_handlers.create_project(
            metadata, project_manager=await _get_project_manager(), actor=approver
        )
    except ProjectExists:
        raise ConflictError(f"a project named '{metadata.name}' already exists")


async def _close_project(request: Request, approver: User) -> None:
    """Closes the project of a close-project request, keeping a copy of it

    Args:
        request: the close-project request
        approver: the user approving the request

    Raises:
        NotFoundError: project {id} not found
    """
    project = await _get_project(request.resource_id)
    project_manager = await _get_project_manager()
    await project_manager.delete(project, is_superuser=True)


async def _transfer_project(request: Request, approver: User) -> None:
    """Makes the user named in a transfer-project request the admin of its project

    Args:
        request: the transfer-project request
        approver: the user approving the request

    Raises:
        NotFoundError: project {id} not found
        NotFoundError: no users of emails {emails}
    """
    metadata = cast(TransferProjectMetadata, request.metadata)
    project = await _get_project(request.resource_id)
    email_id_map = await _get_user_email_id_map([metadata.admin_email])
    new_admin_id = email_id_map[metadata.admin_email]
    await Project.find_one(Project.id == project.id).update(
        Set({Project.admin_id: new_admin_id}),
        AddToSet({Project.user_ids: new_admin_id}),
    )


async def _add_qpu_seconds(request: Request, approver: User) -> None:
    """Adds the seconds asked for in a project-qpu-seconds request to its project

    Args:
        request: the project-qpu-seconds request
        approver: the user approving the request

    Raises:
        NotFoundError: project {id} not found
    """
    metadata = cast(ProjectQpuSecondsMetadata, request.metadata)
    project = await _get_project(request.resource_id)
    project_db = await get_project_db()
    await project_db.increment_qpu_seconds(project.id, metadata.seconds)


async def _add_project_member(request: Request, approver: User) -> None:
    """Adds the requester of a project-access request to its project

    Args:
        request: the project-access request
        approver: the user approving the request

    Raises:
        NotFoundError: project {id} not found
    """
    project = await _get_project(request.resource_id)
    await Project.find_one(Project.id == project.id).update(
        AddToSet({Project.user_ids: request.requester_id})
    )


async def _get_project(project_id: PydanticObjectId) -> Project:
    """Gets the project of the given ID

    Args:
        project_id: the ID of the project

    Returns:
        the project

    Raises:
        NotFoundError: project {id} not found
    """
    project = await Project.get(project_id)
    if project is None:
        raise NotFoundError(f"project {project_id} not found")

    return project


async def _get_project_manager() -> ProjectAppTokenManager:
    """Gets the manager of the projects"""
    return ProjectAppTokenManager(
        await get_project_db(),
        app_token_db=AppTokenDatabase(),
        user_db=UserDatabase(),
    )


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
