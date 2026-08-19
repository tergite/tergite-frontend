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
"""Per-recipient, event-driven notifications.

Distinct from `services.notices`, which is an admin-authored broadcast channel with its
own expiry and shared dismissal state. The two are merged only for presentation.
"""
from .dtos import (
    ChannelPrefs,
    EmailStatus,
    Notification,
    NotificationAction,
    NotificationPreferences,
    NotificationRead,
    NotificationSeverity,
    NotificationType,
    NotificationUpdate,
)
from .outbox import send_pending, start_sweeper, stop_sweeper
from .service import (
    count_many,
    find_many,
    get_preferences,
    notify,
    on_startup,
    set_all_read,
    set_preferences,
    set_read,
)
from .templates import CHANNEL_POLICY

__all__ = [
    "CHANNEL_POLICY",
    "ChannelPrefs",
    "EmailStatus",
    "Notification",
    "NotificationAction",
    "NotificationPreferences",
    "NotificationRead",
    "NotificationSeverity",
    "NotificationType",
    "NotificationUpdate",
    "count_many",
    "find_many",
    "get_preferences",
    "notify",
    "on_startup",
    "send_pending",
    "set_all_read",
    "set_preferences",
    "set_read",
    "start_sweeper",
    "stop_sweeper",
]
