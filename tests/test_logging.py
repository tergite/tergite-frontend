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

from utils.logging import get_log_level


@pytest.mark.parametrize(
    "environment, level",
    [("production", "INFO"), ("test", "WARNING"), ("development", "DEBUG")],
)
def test_each_environment_logs_from_its_level(environment, level):
    assert get_log_level(environment) == level
