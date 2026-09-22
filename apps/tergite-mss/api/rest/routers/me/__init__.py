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

"""Router for my things"""

from fastapi import APIRouter

from services.auth import APP_TOKEN_AUTH, APP_TOKEN_BACKEND

from .jobs import router as jobs_router
from .notices import router as notices_router
from .requests import router as requests_router
from .profile import router as profile_router

router = APIRouter(prefix="/me")

router.include_router(
    APP_TOKEN_AUTH.get_my_projects_router(),
    prefix="/projects",
    tags=["auth"],
)

router.include_router(
    APP_TOKEN_AUTH.get_app_tokens_router(backend=APP_TOKEN_BACKEND),
    prefix="/tokens",
    tags=["auth"],
)

router.include_router(requests_router, prefix="/requests", tags=["user-requests"])
router.include_router(notices_router, prefix="/notices", tags=["notices"])
router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
router.include_router(profile_router, prefix="/profile", tags=["profile"])
