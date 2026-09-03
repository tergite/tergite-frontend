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
#

from .dtos import (
    EmailStatus,
    Notice,
    NoticePreferences,
    NoticeSeverity,
    NoticeType,
)
from .service import (
    count_many,
    create_system_notice,
    delete_notice,
    find_many,
    get_email_preferences,
    get_one,
    mark_ref_handled,
    on_startup,
    publish_custom_notice,
    set_email_preferences,
    toggle_read_status,
    toggle_read_status_many,
)

__all__ = [
    "EmailStatus",
    "Notice",
    "NoticePreferences",
    "NoticeSeverity",
    "NoticeType",
    "count_many",
    "find_many",
    "get_email_preferences",
    "mark_ref_handled",
    "create_system_notice",
    "publish_custom_notice",
    "on_startup",
    "toggle_read_status_many",
    "set_email_preferences",
    "toggle_read_status",
]
