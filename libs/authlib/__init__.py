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
"""Users and their sessions for FastAPI apps, signed in through OAuth providers

It began as a copy of fastapi-users 14.0.2, stripped to what tergite uses.
"""
from .auth import Auth
from .cookies import SessionCookie
from .errors import (
    AuthError,
    EmailNotAvailable,
    EmailNotPermitted,
    Forbidden,
    InactiveUser,
    InvalidStateToken,
    ProviderNotFound,
    Unauthorized,
    UserAlreadyExists,
    add_exception_handlers,
)
from .models import UserOAuthProtocol, UserProtocol
from .providers import OAuthProvider
from .routers import get_logout_router, get_oauth_router
from .schemas import BaseOAuthAccount, BaseUser
from .tokens import (
    SESSION_AUDIENCE,
    STATE_AUDIENCE,
    SecretType,
    read_session_user_id,
    write_session_token,
)
from .users import get_user, get_user_by_email, sign_in_with_oauth

__all__ = [
    "SESSION_AUDIENCE",
    "STATE_AUDIENCE",
    "Auth",
    "AuthError",
    "BaseOAuthAccount",
    "BaseUser",
    "EmailNotAvailable",
    "EmailNotPermitted",
    "Forbidden",
    "InactiveUser",
    "InvalidStateToken",
    "OAuthProvider",
    "ProviderNotFound",
    "SecretType",
    "SessionCookie",
    "Unauthorized",
    "UserAlreadyExists",
    "UserOAuthProtocol",
    "UserProtocol",
    "add_exception_handlers",
    "get_logout_router",
    "get_oauth_router",
    "get_user",
    "get_user_by_email",
    "read_session_user_id",
    "sign_in_with_oauth",
    "write_session_token",
]
