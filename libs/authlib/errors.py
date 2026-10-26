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
"""The ways auth fails, each answered with its own status and detail

The app registers their handler with `add_exception_handlers`, so authlib raises no
HTTPException of its own.
"""
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AuthError(Exception):
    """A failure of auth, answered with its status code and detail"""

    status_code: int = status.HTTP_400_BAD_REQUEST
    default_detail: Optional[str] = "Bad Request"

    def __init__(self, detail: Optional[str] = None):
        super().__init__(detail)
        self.detail = detail if detail is not None else self.default_detail


class Unauthorized(AuthError):
    """No user is signed in, or the one signed in is inactive"""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Unauthorized"


class Forbidden(AuthError):
    """The signed-in user lacks what the route requires"""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Forbidden"


class ProviderNotFound(AuthError):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Not Found"


class InvalidStateToken(AuthError):
    """The state a provider passed back is missing, invalid or expired"""


class EmailNotAvailable(AuthError):
    """The provider shares no email for the account"""

    default_detail = "OAUTH_NOT_AVAILABLE_EMAIL"


class UserAlreadyExists(AuthError):
    """A user of the account's email exists, and the provider does not link by email"""

    default_detail = "OAUTH_USER_ALREADY_EXISTS"


class InactiveUser(AuthError):
    """The user signing in is inactive"""

    default_detail = "LOGIN_BAD_CREDENTIALS"


class EmailNotPermitted(AuthError):
    """The email does not match the provider's email_regex"""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "user not permitted"


def add_exception_handlers(app: FastAPI) -> None:
    """Answers every AuthError the app's routes raise with its status and detail"""
    app.add_exception_handler(AuthError, _handle_auth_error)


async def _handle_auth_error(request: Request, exp: AuthError) -> JSONResponse:
    return JSONResponse({"detail": exp.detail}, status_code=exp.status_code)
