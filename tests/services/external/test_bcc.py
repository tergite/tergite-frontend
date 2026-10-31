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

import httpx
import pytest

from services.external.bcc.service import _raise_for_bcc_error
from utils.exc import BccHttpError


def test_a_success_raises_nothing():
    _raise_for_bcc_error(httpx.Response(200, json={"detail": "ignored"}))


def test_an_error_raises_its_status_and_detail():
    with pytest.raises(BccHttpError) as info:
        _raise_for_bcc_error(httpx.Response(409, json={"detail": "booked"}))

    assert (info.value.status_code, str(info.value)) == (409, "booked")


def test_an_error_without_json_raises_its_text():
    with pytest.raises(BccHttpError) as info:
        _raise_for_bcc_error(httpx.Response(502, text="Bad Gateway"))

    assert (info.value.status_code, str(info.value)) == (502, "Bad Gateway")
