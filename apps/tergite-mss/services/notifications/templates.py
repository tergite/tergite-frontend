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
from typing import Dict, NamedTuple, Optional

from .dtos import NotificationSeverity, NotificationType


class ChannelPolicy(NamedTuple):
    """Which channels a notification type may use.

    in_app_mandatory means the recipient cannot silence it: anything awaiting their action,
    and any decision on their own request. Silencing those would make the product lie.
    """

    in_app_mandatory: bool
    email_default: bool


class Template(NamedTuple):
    """The copy for one notification type"""

    title: str
    body: str
    severity: NotificationSeverity


CHANNEL_POLICY: Dict[NotificationType, ChannelPolicy] = {
    NotificationType.PROJECT_ACCESS_REQUESTED: ChannelPolicy(True, True),
    NotificationType.PROJECT_ACCESS_APPROVED: ChannelPolicy(True, True),
    NotificationType.PROJECT_ACCESS_REJECTED: ChannelPolicy(True, True),
    NotificationType.QPU_SECONDS_REQUESTED: ChannelPolicy(True, True),
    NotificationType.QPU_SECONDS_GRANTED: ChannelPolicy(True, True),
    NotificationType.QPU_SECONDS_DENIED: ChannelPolicy(True, True),
    NotificationType.PROJECT_MEMBERSHIP_REVOKED: ChannelPolicy(True, True),
    # not awaiting anyone's action, so silenceable; on by default because a depleted
    # project stops accepting jobs and the owner would otherwise find out from a failure
    NotificationType.QPU_SECONDS_LOW: ChannelPolicy(False, True),
    NotificationType.QPU_SECONDS_DEPLETED: ChannelPolicy(False, True),
}

TEMPLATES: Dict[NotificationType, Template] = {
    NotificationType.PROJECT_ACCESS_REQUESTED: Template(
        title="Access request for {project_name}",
        body="{requester_name} is asking to join {project_name}: {reason}",
        severity=NotificationSeverity.INFO,
    ),
    NotificationType.PROJECT_ACCESS_APPROVED: Template(
        title="You were added to {project_name}",
        body="{approver_name} approved your request to join {project_name}.",
        severity=NotificationSeverity.INFO,
    ),
    NotificationType.PROJECT_ACCESS_REJECTED: Template(
        title="Access to {project_name} was declined",
        body="{approver_name} declined your request to join {project_name}. {reason}",
        severity=NotificationSeverity.WARNING,
    ),
    NotificationType.QPU_SECONDS_REQUESTED: Template(
        title="QPU time request for {project_name}",
        body="{requester_name} is asking for {seconds}s on {project_name}: {reason}",
        severity=NotificationSeverity.INFO,
    ),
    NotificationType.QPU_SECONDS_GRANTED: Template(
        title="{seconds}s of QPU time added to {project_name}",
        body="{approver_name} granted {seconds}s of QPU time on {project_name}.",
        severity=NotificationSeverity.INFO,
    ),
    NotificationType.QPU_SECONDS_DENIED: Template(
        title="QPU time for {project_name} was declined",
        body="{approver_name} declined the QPU time request for {project_name}. {reason}",
        severity=NotificationSeverity.WARNING,
    ),
    NotificationType.QPU_SECONDS_LOW: Template(
        title="{project_name} is running low on QPU time",
        body="{project_name} has {seconds}s of QPU time left. Request more before it runs out.",
        severity=NotificationSeverity.WARNING,
    ),
    NotificationType.QPU_SECONDS_DEPLETED: Template(
        title="{project_name} is out of QPU time",
        body="{project_name} has no QPU time left, so its jobs will be rejected until more is granted.",
        severity=NotificationSeverity.CRITICAL,
    ),
    NotificationType.PROJECT_MEMBERSHIP_REVOKED: Template(
        title="You were removed from {project_name}",
        body="{approver_name} removed you from {project_name}. Any API tokens you held for it no longer work.",
        severity=NotificationSeverity.WARNING,
    ),
}


def render_email(title: str, body: str, dashboard_url: Optional[str]) -> str:
    """Wraps a notification's copy in a plain-text email body.

    Plain text only: a handful of short transactional messages does not justify carrying
    an HTML template around, and plain text renders everywhere.

    Args:
        title: the notification title, used as the opening line
        body: the notification body
        dashboard_url: base URL of the dashboard, for the closing link

    Returns:
        the email body
    """
    lines = [title, "", body]
    if dashboard_url:
        lines += ["", f"See it in the dashboard: {dashboard_url.rstrip('/')}"]
    lines += [
        "",
        "--",
        "You are receiving this because of activity on your Tergite account.",
    ]
    return "\n".join(lines)


def render(type_: NotificationType, context: Dict[str, object]) -> Template:
    """Fills the template for the given type with the given context

    Args:
        type_: the notification type whose copy is wanted
        context: the values to interpolate; missing keys render as an empty string

    Returns:
        the Template with title and body interpolated
    """
    template = TEMPLATES[type_]
    safe = _Defaulting(context)
    return Template(
        title=template.title.format_map(safe),
        body=template.body.format_map(safe),
        severity=template.severity,
    )


class _Defaulting(dict):
    """A mapping whose missing keys render as an empty string.

    Keeps a notification from failing to send because one optional field was absent.
    Templates therefore carry no format specs -- numbers arrive pre-formatted.
    """

    def __missing__(self, key: str) -> str:
        return ""
