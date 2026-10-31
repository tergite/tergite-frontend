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

from services.notices import RefType
from services.notices.service import _get_unread_ref_filter

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_each_reference_type_matches_its_ids_among_unread_unexpired_notices():
    notice_filter = _get_unread_ref_filter(
        {RefType.PROJECT: ["p1"], RefType.USER_REQUEST: ["r1", "r2"]}, now=_NOW
    )

    assert notice_filter == {
        "read_at": None,
        "$and": [
            {
                "$or": [
                    {"ref_type": RefType.PROJECT, "ref_id": {"$in": ["p1"]}},
                    {"ref_type": RefType.USER_REQUEST, "ref_id": {"$in": ["r1", "r2"]}},
                ]
            },
            {"$or": [{"expires_at": None}, {"expires_at": {"$gte": _NOW}}]},
        ],
    }
