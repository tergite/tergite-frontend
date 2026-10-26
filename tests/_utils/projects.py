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
"""Test utilities for projects"""
from tests._utils.auth import TEST_PROJECT_ID, TEST_SUPERUSER_ID

PROJECT_QUERIES = [
    ([("is_active", "false")], lambda v: not v.get("is_active", True)),
    (
        [("min_qpu_seconds", "0"), ("max_qpu_seconds", "60000")],
        lambda v: 0 <= v["qpu_seconds"] <= 60000,
    ),
    (
        [("name", "Normal Test"), ("name", "Zero QPU")],
        lambda v: v["name"] in ("Normal Test", "Zero QPU"),
    ),
    (
        [("id", TEST_PROJECT_ID), ("id", "7c445113e77284cef9397c5b")],
        lambda v: str(v["_id"]) in (TEST_PROJECT_ID, "7c445113e77284cef9397c5b"),
    ),
    (
        [("user_ids", TEST_SUPERUSER_ID)],
        lambda v: TEST_SUPERUSER_ID in [str(u) for u in v["user_ids"]],
    ),
    (
        [("is_active", "true"), ("min_qpu_seconds", "1")],
        lambda v: v.get("is_active", True) and v["qpu_seconds"] >= 1,
    ),
]
"""The query params of a projects list and whether a stored project matches them"""
