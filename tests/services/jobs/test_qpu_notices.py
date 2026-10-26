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

import pytest

from services.jobs.service import _choose_qpu_notice
from services.notices import NoticeTypeId


@pytest.mark.parametrize(
    "before, after, expected",
    [
        (700, 500, NoticeTypeId.QPU_SECONDS_LOW),
        (500, 400, None),
        (100, 0, NoticeTypeId.QPU_SECONDS_DEPLETED),
        (700, -5, NoticeTypeId.QPU_SECONDS_DEPLETED),
        (0, -5, None),
        (900, 700, None),
    ],
)
def test_only_crossing_zero_or_the_threshold_alerts(before, after, expected):
    assert _choose_qpu_notice(before, after, threshold=600) == expected
