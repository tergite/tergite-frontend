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
from fastapi import APIRouter, Depends, status

from libs.authlib import models
from libs.authlib.authentication import AuthenticationBackend, Authenticator, Strategy
from libs.authlib.openapi import OpenAPIResponseType


def get_auth_router(
    backend: AuthenticationBackend[models.UP, models.ID],
    authenticator: Authenticator[models.UP, models.ID],
    requires_verification: bool = False,
) -> APIRouter:
    """Generate a router with the logout route for an authentication backend."""
    router = APIRouter()
    get_current_user_token = authenticator.current_user_token(
        active=True, verified=requires_verification
    )

    logout_responses: OpenAPIResponseType = {
        **{
            status.HTTP_401_UNAUTHORIZED: {
                "description": "Missing token or inactive user."
            }
        },
        **backend.transport.get_openapi_logout_responses_success(),
    }

    @router.post(
        "/logout", name=f"auth:{backend.name}.logout", responses=logout_responses
    )
    async def logout(
        user_token: tuple[models.UP, str] = Depends(get_current_user_token),
        strategy: Strategy[models.UP, models.ID] = Depends(backend.get_strategy),
    ):
        user, token = user_token
        return await backend.logout(strategy, user, token)

    return router
