# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2024
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

from api.rest.dependencies import CurrentUserDep
from services.auth import APP_TOKEN_AUTH, APP_TOKEN_BACKEND, User, UserRead

from .jobs import router as jobs_router
from .notices import router as notices_router
from .requests import router as requests_router

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

router.include_router(requests_router)
router.include_router(notices_router)
router.include_router(jobs_router)


@router.get("", tags=["users"], response_model=UserRead)
async def get_my_user_info(user: User = CurrentUserDep):
    """Retrieves the information on the current user"""
    return user.model_dump()
