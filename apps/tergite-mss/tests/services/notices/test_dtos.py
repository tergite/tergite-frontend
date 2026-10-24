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
"""Unit tests for the notice types and templates"""
import pytest

from services.notices import NoticeSeverity, NoticeType
from services.notices.dtos import NoticeTemplate


def test_notice_type_from_str_finds_the_type_of_the_id():
    assert NoticeType.from_str("qpu-seconds-low") is NoticeType.QPU_SECONDS_LOW


def test_notice_type_from_str_raises_key_error_for_an_unknown_id():
    with pytest.raises(KeyError):
        NoticeType.from_str("no-such-type")


def test_notice_template_from_notice_type_accepts_the_id():
    template = NoticeTemplate.from_notice_type("qpu-seconds-depleted")

    assert template.type == "qpu-seconds-depleted"
    assert template.severity == NoticeSeverity.CRITICAL
