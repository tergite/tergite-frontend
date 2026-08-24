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
"""Service for granting QPU seconds to many personal projects at once"""
from typing import Dict, List, Optional, Tuple

from beanie import PydanticObjectId, init_beanie
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

import settings
from services import notifications
from services.auth.projects.database import ProjectDatabase
from services.auth.projects.dtos import Project
from services.auth.users.dtos import User
from services.notifications import NotificationType
from utils.exc import ForbiddenError

from .dtos import (
    GrantTarget,
    QpuSecondsGrant,
    QpuSecondsGrantCreate,
    QpuSecondsGrantReport,
    SkippedTarget,
)

_NO_PERSONAL_PROJECT = "no personal project yet — user has never logged in"
_NO_SUCH_USER = "no such user"


async def grant(
    payload: QpuSecondsGrantCreate,
    granted_by: User,
    idempotency_key: str,
) -> QpuSecondsGrantReport:
    """Adds QPU seconds to many personal projects at once.

    Args:
        payload: how many seconds, to whom, and why
        granted_by: the superuser performing the grant
        idempotency_key: caller-supplied key making a replayed request a no-op

    Returns:
        a report of how many projects were granted and which targets were skipped

    Raises:
        ForbiddenError: a single grant may not exceed {max} seconds
    """
    maximum = settings.CONFIG.projects.max_grant_seconds
    if payload.seconds > maximum:
        raise ForbiddenError(f"a single grant may not exceed {maximum:.0f} seconds")

    existing = await QpuSecondsGrant.find_one({"idempotency_key": idempotency_key})
    if existing is not None:
        return _to_report(existing)

    projects, skipped = await _resolve_targets(payload)

    record = QpuSecondsGrant(
        **payload.model_dump(),
        granted_by=granted_by.id,
        idempotency_key=idempotency_key,
        granted_project_ids=[str(item.id) for item in projects],
        skipped=skipped,
    )
    try:
        await record.create()
    except DuplicateKeyError:
        # a concurrent replay won the race; return whatever it recorded
        winner = await QpuSecondsGrant.find_one({"idempotency_key": idempotency_key})
        return _to_report(winner) if winner else _to_report(record)

    for project in projects:
        # goes through the helper so the low-QPU latch clears with the top-up
        await ProjectDatabase.increment_qpu_seconds(str(project.id), payload.seconds)

    await notifications.notify(
        [PydanticObjectId(project.admin_id) for project in projects],
        NotificationType.QPU_SECONDS_GRANTED,
        context={
            "project_name": "your personal project",
            "approver_name": granted_by.username,
            "seconds": f"{payload.seconds:.0f}",
            "reason": "admin-grant",
        },
    )

    return _to_report(record)


async def get_many(skip: int = 0, limit: Optional[int] = None) -> List[QpuSecondsGrant]:
    """The grant history, newest first

    Args:
        skip: the number of records to skip
        limit: the maximum number of records to return

    Returns:
        the matched grant records
    """
    return (
        await QpuSecondsGrant.find({}, skip=skip, limit=limit)
        .sort("-created_at")
        .to_list()
    )


async def on_startup(db: AsyncIOMotorDatabase):
    """Runs init operations when the application is starting up"""
    await init_beanie(database=db, document_models=[QpuSecondsGrant])


async def _resolve_targets(
    payload: QpuSecondsGrantCreate,
) -> Tuple[List[Project], List[SkippedTarget]]:
    """Finds the personal projects a grant applies to.

    Dormant users are skipped rather than provisioned: a user who has never logged in has
    no personal project, and creating one here would undo the laziness that keeps
    auth_projects free of rows for never-seen invitees.

    Args:
        payload: the grant request

    Returns:
        the projects to increment, and the targets that could not be resolved
    """
    if payload.target == GrantTarget.ALL_PERSONAL_PROJECTS:
        projects = await Project.find({"is_personal": True}).to_list()
        return projects, []

    emails = list(dict.fromkeys(payload.target_emails or []))
    users = await User.find({"email": {"$in": emails}}).to_list()
    by_email: Dict[str, User] = {user.email: user for user in users}

    projects: List[Project] = []
    skipped: List[SkippedTarget] = []
    for email in emails:
        user = by_email.get(email)
        if user is None:
            skipped.append(SkippedTarget(email=email, why=_NO_SUCH_USER))
            continue

        project = await Project.find_one(
            {"admin_id": str(user.id), "is_personal": True}
        )
        if project is None:
            skipped.append(SkippedTarget(email=email, why=_NO_PERSONAL_PROJECT))
            continue

        projects.append(project)

    return projects, skipped


def _to_report(record: QpuSecondsGrant) -> QpuSecondsGrantReport:
    """Summarises a stored grant for the caller"""
    return QpuSecondsGrantReport(
        seconds=record.seconds,
        granted=len(record.granted_project_ids),
        skipped=record.skipped,
    )
