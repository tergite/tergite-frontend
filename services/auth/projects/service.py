# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Projects: their members, their QPU seconds, and their deletion"""
from typing import Any, Dict, List, Optional

from libs.storage import Database, DuplicateKeyError, derive_id
from utils.exc import ForbiddenError

from ..app_tokens import service as app_tokens
from ..users.dtos import User
from ..utils import ensure_short_list
from . import membership
from .dtos import (
    DeletedProject,
    Project,
    ProjectAdminView,
    ProjectCreate,
    ProjectQuery,
    ProjectUpdate,
)
from .exc import ProjectExists, ProjectNotExists


async def get_project(database: Database, project_id: str) -> Project:
    """Gets the project of the given id

    Raises:
        ProjectNotExists: project {id} not found
    """
    project = await database.get(Project, project_id)
    if project is None:
        raise ProjectNotExists(f"project {project_id} not found")
    return project


async def get_project_if_member(
    database: Database, project_id: str, user_id: str
) -> Optional[Project]:
    """Gets the project of the given id if the user is a member, else None"""
    return await database.find_one(Project, {"id": project_id, "user_ids": user_id})


async def find_projects(
    database: Database,
    query: ProjectQuery,
    member_id: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Project]:
    """Finds the projects that fit the query

    Args:
        database: the database where the projects are stored
        query: the values the projects have; its unset fields match anything
        member_id: the user whose projects alone are wanted; None for anyone's
        skip: the number of matched projects to skip
        limit: the most projects to return; None returns all

    Raises:
        TooManyListQueryParams: a list has more than MAX_LIST_QUERY_LEN items
    """
    project_filter: Dict[str, Any] = {}
    if query.ids is not None:
        project_filter["id"] = {"$in": ensure_short_list("id", query.ids)}
    if query.user_ids is not None:
        user_ids = ensure_short_list("user_ids", query.user_ids)
        project_filter["user_ids"] = {"$in": user_ids}
    if query.names is not None:
        project_filter["name"] = {"$in": ensure_short_list("name", query.names)}
    if query.is_active is True:
        # a project stored without is_active is active, as the field defaults to True
        project_filter["is_active"] = {"$ne": False}
    if query.is_active is False:
        project_filter["is_active"] = False

    qpu_seconds: Dict[str, float] = {}
    if query.min_qpu_seconds is not None:
        qpu_seconds["$gte"] = query.min_qpu_seconds
    if query.max_qpu_seconds is not None:
        qpu_seconds["$lte"] = query.max_qpu_seconds
    if qpu_seconds:
        project_filter["qpu_seconds"] = qpu_seconds

    if member_id is not None:
        # in an $and, so that a user_ids query narrows the member's projects
        project_filter = {"$and": [project_filter, {"user_ids": member_id}]}
    return await database.find(Project, filter=project_filter, skip=skip, limit=limit)


async def create_project(
    database: Database, payload: ProjectCreate, actor: User
) -> Project:
    """Creates a project and tells its members about it

    Users of any emails that do not exist yet are created.

    Args:
        database: the database where the projects are stored
        payload: the project to create
        actor: the user creating the project

    Returns:
        the created project

    Raises:
        ProjectExists: a project of the same name exists
    """
    email_id_map = await membership.get_user_email_id_map(
        database, [*payload.user_emails, payload.admin_email]
    )
    admin_id = email_id_map[payload.admin_email]
    user_ids = [email_id_map[email] for email in payload.user_emails]
    if admin_id not in user_ids:
        user_ids.append(admin_id)

    project = Project(
        **payload.model_dump(exclude={"user_emails", "admin_email"}),
        user_ids=user_ids,
        admin_id=admin_id,
    )
    try:
        await database.insert(Project, project)
    except DuplicateKeyError:
        raise ProjectExists()

    await membership.notify_membership_change(database, None, project, actor)
    return project


async def update_project(
    database: Database, project: Project, payload: ProjectUpdate, actor: User
) -> Project:
    """Updates a project, telling the users whose standing changed

    The admin is always a member. A member who leaves loses their app tokens for it.

    Args:
        database: the database where the projects are stored
        project: the project as it is
        payload: the changes, with members and admin named by email
        actor: the superuser making the change

    Returns:
        the updated project
    """
    changes = payload.model_dump(
        exclude={"admin_email", "user_emails"}, exclude_none=True
    )
    emails = [*(payload.user_emails or []), payload.admin_email]
    email_id_map = await membership.get_user_email_id_map(
        database, [email for email in emails if email is not None]
    )

    admin_id = project.admin_id
    if payload.admin_email is not None:
        admin_id = email_id_map[payload.admin_email]
    changes["admin_id"] = admin_id

    if payload.user_emails is not None:
        user_ids = [email_id_map[email] for email in payload.user_emails]
    else:
        user_ids = list(project.user_ids)
    if admin_id not in user_ids:
        user_ids.append(admin_id)
    if user_ids != project.user_ids:
        changes["user_ids"] = user_ids
        await app_tokens.delete_non_member_tokens(database, project.id, user_ids)

    updated_project = await database.update_one(
        Project, {"id": project.id}, {"$set": changes}
    )
    await membership.notify_membership_change(database, project, updated_project, actor)
    return updated_project


async def remove_member(
    database: Database, project: Project, member_id: str, actor: User
) -> Project:
    """Removes a member from a project, revoking their app tokens for it

    Args:
        database: the database where the projects are stored
        project: the project
        member_id: the member to remove
        actor: the project admin or superuser removing them

    Returns:
        the updated project
    """
    user_ids = [user_id for user_id in project.user_ids if user_id != member_id]
    await app_tokens.delete_non_member_tokens(database, project.id, user_ids)
    updated_project = await database.update_one(
        Project, {"id": project.id}, {"$set": {"user_ids": user_ids}}
    )
    await membership.notify_membership_revoked(
        database, updated_project, member_id, actor
    )
    return updated_project


async def delete_project(
    database: Database, project: Project, is_superuser: bool = False
) -> None:
    """Deletes a project, with its app tokens, keeping a copy among the deleted ones

    Args:
        database: the database where the projects are stored
        project: the project to delete
        is_superuser: whether the caller is acting as a superuser; defaults to False
            so a caller that does not say is treated as not

    Raises:
        ForbiddenError: you cannot delete your own personal project
    """
    if project.is_personal and not is_superuser:
        # a personal project is recreated on next login with a fresh allowance, so
        # its owner deleting it would be an allowance farm. Superusers may, for
        # offboarding and erasure.
        raise ForbiddenError("you cannot delete your own personal project")

    await app_tokens.delete_project_tokens(database, project.id)
    await database.delete_one(Project, {"id": project.id})
    deleted_project = DeletedProject(
        **project.model_dump(exclude={"created_at", "updated_at"})
    )
    await database.insert(DeletedProject, deleted_project)


async def ensure_personal_project(
    database: Database, user: User, qpu_seconds: float
) -> Project:
    """Gets the user's personal project, creating it with the given QPU seconds if none

    Its id is computed from the user's, so two logins at once create it only once.

    Args:
        database: the database where the projects are stored
        user: the user whose personal project is required
        qpu_seconds: the QPU seconds a new personal project starts with

    Returns:
        the personal project
    """
    user_id = str(user.id)
    project_id = derive_id(user_id, namespace="project")
    existing = await database.get(Project, project_id)
    if existing is not None:
        return existing

    project = Project(
        id=project_id,
        name=f"{user.username} (personal)",
        description=f"{user.username} personal project",
        qpu_seconds=qpu_seconds,
        admin_id=user_id,
        user_ids=[user_id],
        is_personal=True,
    )
    try:
        return await database.insert(Project, project)
    except DuplicateKeyError:
        return await database.get(Project, project_id)


async def increment_qpu_seconds(
    database: Database, project_id: Optional[str], qpu_seconds: float
) -> Optional[Project]:
    """Increments the QPU seconds of the given project

    Args:
        database: the database where the projects are stored
        project_id: the ID of the project; None matches no project
        qpu_seconds: the seconds to increment by

    Returns:
        the updated project, or None if no project matched
    """
    if project_id is None:
        return None
    return await database.update_one(
        Project, {"id": project_id}, {"$inc": {"qpu_seconds": qpu_seconds}}
    )


async def add_member(database: Database, project_id: str, user_id: str) -> Project:
    """Adds the user to the project's members, if not one already"""
    return await database.update_one(
        Project, {"id": project_id}, {"$addToSet": {"user_ids": user_id}}
    )


async def set_admin(database: Database, project_id: str, user_id: str) -> Project:
    """Makes the user the project's admin, and a member if not one already"""
    return await database.update_one(
        Project,
        {"id": project_id},
        {"$set": {"admin_id": user_id}, "$addToSet": {"user_ids": user_id}},
    )


async def get_admin_view(database: Database, project: Project) -> ProjectAdminView:
    """Gets the project as an admin sees it, its admin and members named by email

    Raises:
        KeyError: a member's user does not exist
    """
    id_email_map = await membership.get_user_id_email_map(
        database, [*project.user_ids, project.admin_id]
    )
    return ProjectAdminView(
        **project.model_dump(exclude={"user_emails", "admin_email"}),
        user_emails=[id_email_map[user_id] for user_id in project.user_ids],
        admin_email=id_email_map[project.admin_id],
    )
