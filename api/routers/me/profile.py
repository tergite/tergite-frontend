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

"""Router for my profile"""

from fastapi import APIRouter

from api.dependencies import CurrentUserDep
from services.auth import UserRead

router = APIRouter()


@router.get("", response_model=UserRead)
async def get_my_user_profile(user: CurrentUserDep):
    """Retrieves the information on the current user

    Args:
        user: the current logged-in user

    Returns:
        the user's profile
    """
    return UserRead.model_validate(user)
