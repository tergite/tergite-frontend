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

from libs.storage import Database
from services import notices
from services.notices import NoticeTypeId, ProjectRequestContext, RefType

from ..users.dtos import User
from .dtos import Project


async def notify_membership_change(
    database: Database,
    initial_project: Optional[Project],
    final_project: Project,
    actor: User,
) -> None:
    """Tells users whose standing on a project changed

    An admin editing a project replaces the member list wholesale, so who gained and who
    lost access is only visible as a diff against the previous document.

    Args:
        database: the database where the notices are stored
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
        database,
        user_ids=list(new_ids - old_ids),
        notice_type=NoticeTypeId.PROJECT_MEMBERSHIP_GRANTED,
        context=context,
        ref_type=RefType.PROJECT,
        ref_id=final_project.id,
    )

    await notices.create_system_notice(
        database,
        user_ids=list(old_ids - new_ids),
        notice_type=NoticeTypeId.PROJECT_MEMBERSHIP_REVOKED,
        context=context,
        ref_type=RefType.PROJECT,
        ref_id=final_project.id,
    )

    old_admin = initial_project.admin_id if initial_project else None
    if final_project.admin_id != old_admin:
        await notices.create_system_notice(
            database,
            user_ids=[final_project.admin_id],
            notice_type=NoticeTypeId.PROJECT_ADMIN_ASSIGNED,
            context=context,
            ref_type=RefType.PROJECT,
            ref_id=final_project.id,
        )


async def notify_membership_revoked(
    database: Database, project: Project, member_id: str, actor: User
) -> None:
    """Tells a removed member they no longer belong to the project

    Args:
        database: the database where the notices are stored
        project: the project the member was removed from
        member_id: the id of the removed member
        actor: the project admin or superuser who removed them
    """
    await notices.create_system_notice(
        database,
        user_ids=[member_id],
        notice_type=NoticeTypeId.PROJECT_MEMBERSHIP_REVOKED,
        context=ProjectRequestContext(
            project_id=str(project.id),
            project_name=project.name,
            approver_name=actor.username,
        ),
        ref_type=RefType.PROJECT,
        ref_id=project.id,
    )


async def get_user_id_email_map(
    database: Database, user_ids: List[str]
) -> Dict[str, str]:
    """Gets the emails of the users of the given ids, keyed by id

    Args:
        database: the database where the users are stored
        user_ids: the ids of the users

    Returns:
        the email of each user found, keyed by their id
    """
    users = await database.find(User, filter={"id": {"$in": list(user_ids)}})
    return {user.id: user.email for user in users}


async def get_user_email_id_map(
    database: Database, user_emails: List[str]
) -> Dict[str, str]:
    """Gets the ids of the users of the given emails, keyed by each email as given

    Emails match in any case. It creates a user for each email that has none yet.

    Args:
        database: the database where the users are stored
        user_emails: the emails of the users

    Returns:
        the id of each user, keyed by their email as given
    """
    if len(user_emails) == 0:
        return {}

    users = await database.find(User, filter={"email": {"$in": list(user_emails)}})
    id_by_lower_email = {user.email.lower(): user.id for user in users}
    missing_emails = {
        email.lower(): email
        for email in user_emails
        if email.lower() not in id_by_lower_email
    }
    if missing_emails:
        new_users = [User(email=email) for email in missing_emails.values()]
        inserted_users = await database.insert_many(User, new_users)
        id_by_lower_email.update(
            {user.email.lower(): user.id for user in inserted_users}
        )

    return {email: id_by_lower_email[email.lower()] for email in user_emails}
