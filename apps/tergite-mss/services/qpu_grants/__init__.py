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
"""Bulk QPU-second grants to personal projects.

Recorded per operation rather than per recipient, so a replayed request is a no-op.
"""
from .dtos import (
    GrantTarget,
    QpuSecondsGrant,
    QpuSecondsGrantCreate,
    QpuSecondsGrantReport,
    SkippedTarget,
)
from .service import get_many, grant, on_startup

__all__ = [
    "GrantTarget",
    "QpuSecondsGrant",
    "QpuSecondsGrantCreate",
    "QpuSecondsGrantReport",
    "SkippedTarget",
    "get_many",
    "grant",
    "on_startup",
]
