# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Routes for admin related operations"""

from fastapi import APIRouter

from .recalibration import router as recalibration_router
from .switch import router as switch_router
from .users import router as users_router

router = APIRouter()

router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(
    recalibration_router, prefix="/recalibration", tags=["recalibration"]
)
router.include_router(switch_router, prefix="/switch", tags=["switch"])
