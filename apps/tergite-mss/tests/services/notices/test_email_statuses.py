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

from services.notices import EmailStatus
from services.notices.service import _get_email_status_map


def test_users_get_email_unless_they_opted_out():
    statuses = _get_email_status_map(
        ["a", "b", "c"], {"a": True, "b": False}, is_email_enabled=True
    )

    assert statuses == {
        "a": EmailStatus.PENDING,
        "b": EmailStatus.NOT_APPLICABLE,
        "c": EmailStatus.PENDING,
    }


def test_no_user_gets_email_when_email_is_off():
    statuses = _get_email_status_map(["a"], {"a": True}, is_email_enabled=False)

    assert statuses == {"a": EmailStatus.NOT_APPLICABLE}
