# This code is part of Tergite
#
# (C) Copyright François Voron 2019 (fastapi-users 14.0.2, MIT licence; see libs/authlib/LICENSE)
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
from libs.authlib.router.auth import get_auth_router
from libs.authlib.router.common import ErrorCode
from libs.authlib.router.oauth import get_oauth_router
from libs.authlib.router.register import get_register_router
from libs.authlib.router.reset import get_reset_password_router
from libs.authlib.router.users import get_users_router
from libs.authlib.router.verify import get_verify_router

__all__ = [
    "ErrorCode",
    "get_auth_router",
    "get_oauth_router",
    "get_register_router",
    "get_reset_password_router",
    "get_users_router",
    "get_verify_router",
]
