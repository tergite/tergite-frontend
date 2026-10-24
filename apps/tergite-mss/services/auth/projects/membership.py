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
"""Who belongs to a project: telling users their standing changed, and naming them"""
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from fastapi_users.password import PasswordHelper
from pydantic import BaseModel, Field

from services import notices
from services.notices import NoticeType, ProjectRequestContext, RefType

from ..users.dtos import User
from .dtos import Project

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


async def notify_membership_revoked(
    project: Project, member_id: str, actor: User
) -> None:
    """Tells a removed member they no longer belong to the project"""
    await notices.create_system_notice(
        user_ids=[member_id],
        notice_type=NoticeType.PROJECT_MEMBERSHIP_REVOKED.id,
        context=ProjectRequestContext(
            project_id=str(project.id),
            project_name=project.name,
            approver_name=actor.username,
        ),
        ref_type=RefType.PROJECT,
        ref_id=project.id,
    )


async def get_user_id_email_map(user_ids: List[str]) -> Dict[str, str]:
    """Gets the emails of the users of the given ids, keyed by id"""
    object_ids = [PydanticObjectId(v) for v in user_ids]
    users = await User.find(
        {"_id": {"$in": object_ids}}, projection_model=_TrimmedUser
    ).to_list()
    return {str(v.id): v.email for v in users}


async def get_user_email_id_map(user_emails: List[str]) -> Dict[str, str]:
    """Gets the ids of the users of the given emails, keyed by email

    It creates a user for each email that has none yet.
    """
    if len(user_emails) == 0:
        return {}

    users = await User.find({"email": {"$in": user_emails}}).to_list()
    email_id_map = {v.email: str(v.id) for v in users}

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
        for email, user_id in zip(new_emails, inserted_users.inserted_ids):
            email_id_map[email] = str(user_id)

    return email_id_map


class _TrimmedUser(BaseModel):
    """A user object with only email and _id"""

    email: str
    id: PydanticObjectId = Field(alias="_id")
