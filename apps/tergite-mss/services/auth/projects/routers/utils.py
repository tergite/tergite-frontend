# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Module containing utilities for the routers"""
from typing import Dict, List, Optional, Union

from beanie import PydanticObjectId
from fastapi_users.password import PasswordHelper
from pydantic import BaseModel, Field

from services import notices
from services.notices import NoticeType

from ....notices.dtos import ProjectRequestContext, RefType
from ...users.dtos import User
from ..dtos import (
    Project,
    ProjectAdminView,
    ProjectCreate,
    ProjectPartial,
    ProjectUpdate,
)

_password_helper = PasswordHelper()


async def notify_membership_change(
    initial_project: Optional[Project], final_project: Project, actor: User
) -> None:
    """Tells users whose standing on a project changed

    An admin editing a project replaces the member list wholesale, so who gained and who
    lost access is only visible as a diff against the previous document.

    Args:
        initial_project: the project as it was, or None when it has just been created
        final_project: the project as it now is
        actor: the superuser who made the change
    """
    context = ProjectRequestContext(
        project_id=str(final_project.id),
        project_name=final_project.name,
        approver_name=actor.username,
    )
    old_ids = set(initial_project.user_ids) if initial_project else set()
    new_ids = set(final_project.user_ids)

    await notices.create_system_notice(
        user_ids=list(new_ids - old_ids),
        notice_type=NoticeType.PROJECT_MEMBERSHIP_GRANTED.id,
        context=context,
        ref_type=RefType.PROJECT,
        ref_id=final_project.id,
    )

    await notices.create_system_notice(
        user_ids=list(old_ids - new_ids),
        notice_type=NoticeType.PROJECT_MEMBERSHIP_REVOKED.id,
        context=context,
        ref_type=RefType.PROJECT,
        ref_id=final_project.id,
    )

    old_admin = initial_project.admin_id if initial_project else None
    if final_project.admin_id != old_admin:
        await notices.create_system_notice(
            user_ids=[final_project.admin_id],
            notice_type=NoticeType.PROJECT_ADMIN_ASSIGNED.id,
            context=context,
            ref_type=RefType.PROJECT,
            ref_id=final_project.id,
        )


async def prepare_partial_project(
    project: Project, payload: ProjectUpdate
) -> ProjectPartial:
    """Prepares the partial project for updating the project

    It replaces user_emails and admin_email with user ids

    Args:
        project: the project to update
        payload: the payload to convert

    Returns:
        the ProjectPartial instance with proper user_ids and admin_id
    """
    is_user_ids_updating = payload.user_emails is not None
    is_admin_id_updating = payload.admin_email is not None

    user_emails = (payload.user_emails or []) + [payload.admin_email]
    user_emails = [k for k in user_emails if k is not None]
    email_id_map = await _get_user_email_id_map(user_emails)
    user_ids: Optional[List[PydanticObjectId]] = None

    admin_id = project.admin_id
    if is_admin_id_updating:
        admin_id = email_id_map[payload.admin_email]

    if is_user_ids_updating:
        user_ids = [email_id_map[email] for email in payload.user_emails]

    if is_user_ids_updating and admin_id not in user_ids:
        user_ids.append(admin_id)

    if not is_user_ids_updating and admin_id not in project.user_ids:
        user_ids = [*project.user_ids, admin_id]

    kwargs = payload.model_dump(exclude={"admin_email", "user_emails"})
    return ProjectPartial(**kwargs, user_ids=user_ids, admin_id=admin_id)


async def prepare_new_project(payload: ProjectCreate) -> Project:
    """Prepares a new Project instance from a ProjectCreate instance

    Args:
        payload: the payload to convert

    Returns:
        the Project instance
    """
    all_emails = [*payload.user_emails, payload.admin_email]
    email_id_map = await _get_user_email_id_map(all_emails)

    user_ids = [email_id_map[email] for email in payload.user_emails]
    admin_id = email_id_map[payload.admin_email]

    if admin_id not in user_ids:
        user_ids.append(admin_id)

    kwargs = payload.model_dump(exclude={"user_emails", "admin_email"})
    return Project(**kwargs, user_ids=user_ids, admin_id=admin_id)


async def get_full_admin_project(
    project: Union[ProjectAdminView, Project],
) -> ProjectAdminView:
    """Returns a project admin view with user_emails and admin_email fields filled

    Args:
        project: the admin project to enhance

    Returns:
        the enhanced admin project

    Raises:
        KeyError: user id does not exist in database
    """
    id_email_map = await _get_user_id_email_map([*project.user_ids, project.admin_id])
    props = project.model_dump(exclude={"user_emails", "admin_email"})
    user_emails = [id_email_map[v] for v in project.user_ids]
    admin_email = id_email_map[project.admin_id]
    return ProjectAdminView(**props, user_emails=user_emails, admin_email=admin_email)


class _TrimmedUser(BaseModel):
    """A user object with only email and _id"""

    email: str
    id: PydanticObjectId = Field(alias="_id")


async def _get_user_id_email_map(
    user_ids: List[PydanticObjectId],
) -> Dict[PydanticObjectId, str]:
    """Gets the user emails for the given user ids as a map

    Args:
        user_ids: the ids of the users

    Returns:
        the map of the user id and email
    """
    users = await User.find(
        {"_id": {"$in": user_ids}}, projection_model=_TrimmedUser
    ).to_list()
    return {v.id: v.email for v in users}


async def _get_user_email_id_map(
    user_emails: List[str],
) -> Dict[str, PydanticObjectId]:
    """Generates a map of user email and their id

    It creates any users for emails whose users don't exist

    Args:
        user_emails: the emails of the users

    Returns:
        the map of the user emails and their corresponding user ids
    """
    if len(user_emails) == 0:
        # return without doing any db requests
        return {}

    users = await User.find({"email": {"$in": user_emails}}).to_list()
    email_id_map = {v.email: v.id for v in users}

    # create any users who don't exist yet
    new_user_ids = []
    new_emails = [email for email in user_emails if email_id_map.get(email) is None]
    new_users = [
        User(
            email=email,
            hashed_password=_password_helper.hash(_password_helper.generate()),
        )
        for email in new_emails
    ]
    if len(new_users) > 0:
        inserted_users = await User.insert_many(new_users, ordered=True)
        new_user_ids = inserted_users.inserted_ids

    # update the email map
    email_id_map.update(
        {email: PydanticObjectId(_id) for email, _id in zip(new_emails, new_user_ids)}
    )

    return email_id_map
