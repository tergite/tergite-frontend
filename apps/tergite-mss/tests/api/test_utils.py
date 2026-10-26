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

from api.utils import _check_nonce_age


def test_a_fresh_nonce_passes():
    _check_nonce_age(100.0, now=150.0, ttl=60)


def test_a_nonce_older_than_the_ttl_fails():
    with pytest.raises(ValueError, match="older than 60 seconds"):
        _check_nonce_age(100.0, now=161.0, ttl=60)


def test_a_nonce_from_the_future_fails():
    with pytest.raises(ValueError, match="in the future"):
        _check_nonce_age(100.0, now=99.0, ttl=60)
