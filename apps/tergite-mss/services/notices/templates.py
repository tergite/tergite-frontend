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
"""Per-type notification copy and channel policy.

Plain format strings rather than a template engine: a handful of short messages does not
justify the dependency.
"""
from typing import Dict

from .dtos import NoticeSeverity, NoticeTemplate, NoticeTemplateInDb, NoticeType

_DEFAULT_TEMPLATES: Dict[NoticeType, NoticeTemplate] = {
    NoticeType.PROJECT_ACCESS_REQUESTED: NoticeTemplate(
        title="Access request for {project_name}",
        body="{requester_name} is asking to join {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
    ),
    NoticeType.PROJECT_ACCESS_APPROVED: NoticeTemplate(
        title="You were added to {project_name}",
        body="{approver_name} approved your request to join {project_name}.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeType.PROJECT_ACCESS_REJECTED: NoticeTemplate(
        title="Access to {project_name} was declined",
        body="{approver_name} declined your request to join {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeType.QPU_SECONDS_REQUESTED: NoticeTemplate(
        title="QPU time request for {project_name}",
        body="{requester_name} is asking for {seconds}s on {project_name}: {reason}",
        severity=NoticeSeverity.INFO,
    ),
    NoticeType.QPU_SECONDS_GRANTED: NoticeTemplate(
        title="{seconds}s of QPU time added to {project_name}",
        body="{approver_name} granted {seconds}s of QPU time on {project_name}.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeType.QPU_SECONDS_DENIED: NoticeTemplate(
        title="QPU time for {project_name} was declined",
        body="{approver_name} declined the QPU time request for {project_name}. {reason}",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeType.QPU_SECONDS_LOW: NoticeTemplate(
        title="{project_name} is running low on QPU time",
        body="{project_name} has {seconds}s of QPU time left. Request more before it runs out.",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeType.QPU_SECONDS_DEPLETED: NoticeTemplate(
        title="{project_name} is out of QPU time",
        body="{project_name} has no QPU time left, so its jobs will be rejected until more is granted.",
        severity=NoticeSeverity.CRITICAL,
    ),
    NoticeType.PROJECT_MEMBERSHIP_REVOKED: NoticeTemplate(
        title="You were removed from {project_name}",
        body="{approver_name} removed you from {project_name}. Any API tokens you held for it no longer work.",
        severity=NoticeSeverity.WARNING,
    ),
    NoticeType.PROJECT_MEMBERSHIP_GRANTED: NoticeTemplate(
        title="You were added to {project_name}",
        body="{approver_name} added you to {project_name} ({project_ext_id}). You can now create API tokens for it.",
        severity=NoticeSeverity.INFO,
    ),
    NoticeType.PROJECT_ADMIN_ASSIGNED: NoticeTemplate(
        title="You now administer {project_name}",
        body="{approver_name} made you the admin of {project_name} ({project_ext_id}). Requests to join it come to you.",
        severity=NoticeSeverity.INFO,
    ),
}


class _NoKeyErrorDict(dict):
    """A dictionary that never has a KeyError because missing keys return an empty string.

    Keeps a notification from failing to send because one optional field was absent.
    Templates therefore carry no format specs -- numbers arrive pre-formatted.
    """

    def __missing__(self, key: str) -> str:
        return ""


async def get_template(notice_type: NoticeType, context: dict) -> NoticeTemplate:
    """Extracts the notice template from a given notice type and context.

    Args:
        notice_type: the type of notice
        context: the context for the template

    Returns:
        the Template with title and body interpolated
    """
    template = await NoticeTemplateInDb.find_one(NoticeTemplateInDb.type == notice_type)
    if not template:
        template = _DEFAULT_TEMPLATES[notice_type]

    lenient_context = _NoKeyErrorDict(context)
    return NoticeTemplate(
        title=template.title.format_map(lenient_context),
        body=template.body.format_map(lenient_context),
        severity=template.severity,
    )
