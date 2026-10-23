# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2024, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Router for admins"""

from fastapi import APIRouter

from api.rest.auth import APP_TOKEN_AUTH

from .bcc import router as bcc_router
from .notices import router as notices_router
from .users import router as users_router

router = APIRouter(prefix="/admin")

router.include_router(
    APP_TOKEN_AUTH.get_projects_router(),
    prefix="/projects",
    tags=["projects"],
)

router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(notices_router, prefix="/notices", tags=["notices"])
router.include_router(bcc_router, prefix="/bcc", tags=["bcc"])
