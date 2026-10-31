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

from datetime import datetime, timezone

from libs.storage import generate_id
from services.notices import NoticeQuery, NoticeTypeId
from services.notices.service import _get_notice_filter

_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
_USER_ID = generate_id()


def test_no_constraints_match_every_notice():
    assert _get_notice_filter(NoticeQuery()) == {}


def test_a_user_sees_their_direct_and_broadcast_notices_not_dismissed():
    assert _get_notice_filter(NoticeQuery(user_id=_USER_ID)) == {
        "user_id": {"$in": [_USER_ID, None]},
        "$and": [{"dismissed_by": {"$nin": [_USER_ID]}}],
    }


def test_ranges_and_types_become_operators():
    query = NoticeQuery(
        min_start_utc=_START, max_expires_utc=_START, types=[NoticeTypeId.CUSTOM]
    )

    assert _get_notice_filter(query) == {
        "starts_at": {"$gte": _START},
        "expires_at": {"$lte": _START},
        "type": {"$in": [NoticeTypeId.CUSTOM]},
    }


def test_read_notices_hold_the_user_in_dismissed_by():
    query = NoticeQuery(user_id=_USER_ID, should_include_dismissed=True, is_read=True)

    assert _get_notice_filter(query) == {
        "user_id": {"$in": [_USER_ID, None]},
        "$and": [{"dismissed_by": _USER_ID}],
    }
