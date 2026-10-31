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

"""Routes for the current user's notices and their delivery preferences"""

from fastapi import APIRouter

from .notices import router as notices_router
from .preferences import router as preferences_router

router = APIRouter()

router.include_router(
    preferences_router, prefix="/preferences", tags=["notices-preferences"]
)
router.include_router(notices_router, prefix="", tags=["notices"])
