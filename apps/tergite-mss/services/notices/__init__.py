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
    CustomNoticeCreate,
    EmailStatus,
    Notice,
    NoticePreferences,
    NoticeSeverity,
    NoticeTemplate,
    NoticeType,
    NoticeTypeId,
)
from .service import (
    clear_notices_by_reference,
    count_many,
    create_system_notice,
    delete_notice,
    find_many,
    get_email_preferences,
    get_one,
    on_startup,
    publish_custom_notice,
    set_email_preferences,
    set_read_status,
    set_read_status_many,
)

SCHEMAS = (Notice, NoticePreferences, NoticeTemplate)

__all__ = [
    "SCHEMAS",
    "NoticeTemplate",
    "CustomNoticeCreate",
    "EmailStatus",
    "Notice",
    "NoticePreferences",
    "NoticeSeverity",
    "NoticeType",
    "NoticeTypeId",
    "count_many",
    "delete_notice",
    "get_one",
    "find_many",
    "get_email_preferences",
    "clear_notices_by_reference",
    "create_system_notice",
    "publish_custom_notice",
    "on_startup",
    "set_read_status_many",
    "set_email_preferences",
    "set_read_status",
]
