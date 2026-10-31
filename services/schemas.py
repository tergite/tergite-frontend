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
"""Every service's schemas, which the one Database and the migrations are made of"""
from typing import Tuple, Type

from libs.storage import Schema
from services import auth, bcc_nonces, calibration, devices, jobs, notices, requests

SCHEMAS: Tuple[Type[Schema], ...] = (
    *auth.SCHEMAS,
    *bcc_nonces.SCHEMAS,
    *calibration.SCHEMAS,
    *devices.SCHEMAS,
    *jobs.SCHEMAS,
    *notices.SCHEMAS,
    *requests.SCHEMAS,
)
