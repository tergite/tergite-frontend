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

from libs.storage import Database
from services import auth
from services.auth import Project, ProjectCreate, ProjectExists, User
from utils.exc import ConflictError, NotFoundError

from .dtos import (
    CreateProjectMetadata,
    ProjectQpuSecondsMetadata,
    Request,
    RequestType,
    TransferProjectMetadata,
)

type Action = Callable[[Database, Request, User], Coroutine[Any, Any, None]]
"""An action that approving a request does, given the database, request and approver"""


async def do_many_actions(
    database: Database, requests: List[Request], approver: User
) -> None:
    """Does the actions of multiple requests, each according to its type

    Args:
        database: the database where the projects are stored
        requests: The requests to do that are to be acted on
        approver: The user who is supposed to approve the request

    Raises:
        ExceptionGroup: errors doing bulk actions
            ValueError: no action for request type {type}
            NotFoundError: project {id} not found
            NotFoundError: no users of emails {emails}
            ConflictError: a project named '{name}' already exists
    """
    tasks = [_do_action(database, req, approver) for req in requests]

    resp = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [item for item in resp if isinstance(item, Exception)]

    if errors:
        raise ExceptionGroup("errors doing bulk action", errors)


async def _do_action(database: Database, request: Request, approver: User) -> None:
    """Does what the given request asks for, as it is being approved

    Args:
        database: the database where the projects are stored
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
        RequestType.PROJECT_PULSE_ACCESS: _set_pulse_allowed,
        RequestType.PROJECT_ACCESS: _add_project_member,
    }

    try:
        action = action_map[request.type]
    except KeyError:
        raise ValueError(f"no action for request type {request.type}")

    await action(database, request, approver)


async def _create_project(database: Database, request: Request, approver: User) -> None:
    """Creates the project described in the metadata of a create-project request

    Users of any emails that do not exist yet are created, as when a superuser
    creates the project directly.

    Args:
        database: the database where the projects are stored
        request: the create-project request
        approver: the user approving the request

    Raises:
        ConflictError: a project named '{name}' already exists
    """
    metadata = cast(CreateProjectMetadata, request.metadata)
    try:
        project = ProjectCreate(**metadata.model_dump(exclude={"resource"}))
        await auth.create_project(database, project, actor=approver)
    except ProjectExists:
        raise ConflictError(f"a project named '{metadata.name}' already exists")


async def _close_project(database: Database, request: Request, approver: User) -> None:
    """Closes the project of a close-project request, keeping a copy of it

    Args:
        database: the database where the projects are stored
        request: the close-project request
        approver: the user approving the request

    Raises:
        NotFoundError: project {id} not found
    """
    project = await _get_project(database, request.resource_id)
    await auth.delete_project(database, project, is_superuser=True)


async def _transfer_project(
    database: Database, request: Request, approver: User
) -> None:
    """Makes the user named in a transfer-project request the admin of its project

    Args:
        database: the database where the projects are stored
        request: the transfer-project request
        approver: the user approving the request

    Raises:
        NotFoundError: project {id} not found
        NotFoundError: no users of emails {emails}
    """
    metadata = cast(TransferProjectMetadata, request.metadata)
    project = await _get_project(database, request.resource_id)
    email_id_map = await _get_user_email_id_map(database, [metadata.admin_email])
    await auth.set_admin(database, project.id, email_id_map[metadata.admin_email])


async def _add_qpu_seconds(
    database: Database, request: Request, approver: User
) -> None:
    """Adds the seconds asked for in a project-qpu-seconds request to its project

    Args:
        database: the database where the projects are stored
        request: the project-qpu-seconds request
        approver: the user approving the request

    Raises:
        NotFoundError: project {id} not found
    """
    metadata = cast(ProjectQpuSecondsMetadata, request.metadata)
    project = await _get_project(database, request.resource_id)
    await auth.increment_qpu_seconds(database, project.id, metadata.seconds)


async def _set_pulse_allowed(
    database: Database, request: Request, approver: User
) -> None:
    """Lets the project of a project-pulse-access request send pulse-level jobs

    Args:
        database: the database where the projects are stored
        request: the project-pulse-access request
        approver: the user approving the request

    Raises:
        NotFoundError: project {id} not found
    """
    project = await _get_project(database, request.resource_id)
    await auth.set_pulse_allowed(database, project.id)


async def _add_project_member(
    database: Database, request: Request, approver: User
) -> None:
    """Adds the requester of a project-access request to its project

    Args:
        database: the database where the projects are stored
        request: the project-access request
        approver: the user approving the request

    Raises:
        NotFoundError: project {id} not found
    """
    project = await _get_project(database, request.resource_id)
    await auth.add_member(database, project.id, request.requester_id)


async def _get_project(database: Database, project_id: str) -> Project:
    """Gets the project of the given ID

    Raises:
        NotFoundError: project {id} not found
    """
    try:
        return await auth.get_project(database, project_id)
    except auth.ProjectNotExists:
        raise NotFoundError(f"project {project_id} not found")


async def _get_user_email_id_map(
    database: Database, emails: Sequence[str]
) -> Dict[str, str]:
    """Gets the IDs of the users of the given emails, keyed by each email as given

    Emails match in any case.

    Args:
        database: the database where the users are kept
        emails: the emails of the users

    Returns:
        the map of email to user ID

    Raises:
        NotFoundError: no users of emails {emails}
    """
    users = await database.find(User, filter={"email": {"$in": list(emails)}})
    id_by_lower_email = {user.email.lower(): user.id for user in users}
    missing_emails = [
        email for email in emails if email.lower() not in id_by_lower_email
    ]
    if missing_emails:
        raise NotFoundError(f"no users of emails {missing_emails}")

    return {email: id_by_lower_email[email.lower()] for email in emails}
