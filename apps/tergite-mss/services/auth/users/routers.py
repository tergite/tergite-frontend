# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
from typing import Dict, List, Optional, Tuple

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from fastapi_users import BaseUserManager, models
from fastapi_users.authentication import AuthenticationBackend, Authenticator, Strategy
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.jwt import SecretType, decode_jwt
from fastapi_users.manager import UserManagerDependency
from fastapi_users.openapi import OpenAPIResponseType
from fastapi_users.router import ErrorCode
from fastapi_users.router.common import ErrorModel
from fastapi_users.router.oauth import (
    STATE_TOKEN_AUDIENCE,
    OAuth2AuthorizeResponse,
    generate_state_token,
)
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback
from httpx_oauth.oauth2 import BaseOAuth2, OAuth2Token


def get_oauth_router(
    oauth_client: BaseOAuth2,
    backend: AuthenticationBackend,
    get_user_manager: UserManagerDependency[models.UP, models.ID],
    state_secret: SecretType,
    redirect_url: Optional[str] = None,
    associate_by_email: bool = False,
    is_verified_by_default: bool = False,
) -> APIRouter:
    """Generate a router with the OAuth routes."""
    router = APIRouter()
    callback_route_name = f"oauth:{oauth_client.name}.{backend.name}.callback"

    if redirect_url is not None:
        oauth2_authorize_callback = OAuth2AuthorizeCallback(
            oauth_client,
            redirect_url=redirect_url,
        )
    else:
        oauth2_authorize_callback = OAuth2AuthorizeCallback(
            oauth_client,
            route_name=callback_route_name,
        )

    async def get_authorization_url(
        request: Request, scopes: Optional[List[str]], _next: Optional[str]
    ) -> str:
        """Gets the authorization url for this Oauth2 provider

        Args:
            request: the FastAPI request object
            scopes: the Oauth2 scopes
            _next: the url to redirect to after successful authentication

        Returns:
            the authorization url
        """
        if redirect_url is not None:
            authorize_redirect_url = redirect_url
        else:
            authorize_redirect_url = str(request.url_for(callback_route_name))

        state_data: Dict[str, str] = {"next": _next}
        state = generate_state_token(state_data, state_secret)
        return await oauth_client.get_authorization_url(
            authorize_redirect_url,
            state,
            scopes,
        )

    @router.get(
        "/authorize",
        name=f"oauth:{oauth_client.name}.{backend.name}.authorize",
        response_model=OAuth2AuthorizeResponse,
    )
    async def authorize(
        request: Request,
        scopes: List[str] = Query(None),
        _next: str = Query(None, alias="next"),
    ) -> OAuth2AuthorizeResponse:
        authorization_url = await get_authorization_url(
            request,
            scopes,
            _next,
        )

        return OAuth2AuthorizeResponse(authorization_url=authorization_url)

    @router.get(
        "/auto-authorize",
        name=f"oauth:{oauth_client.name}.{backend.name}.authorize",
        response_class=RedirectResponse,
    )
    async def auto_authorize(
        request: Request,
        scopes: List[str] = Query(None),
        _next: str = Query(None, alias="next"),
    ):
        """Automatically redirects to the authorization URL"""
        return await get_authorization_url(
            request,
            scopes,
            _next,
        )

    @router.get(
        "/callback",
        name=callback_route_name,
        description="The response varies based on the authentication backend used.",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            **backend.transport.get_openapi_login_responses_success(),
            status.HTTP_307_TEMPORARY_REDIRECT: {
                "description": "Logged in; redirects to the `next` URL in the state."
            },
        },
    )
    async def callback(
        request: Request,
        access_token_state: Tuple[OAuth2Token, str] = Depends(
            oauth2_authorize_callback
        ),
        user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
        strategy: Strategy[models.UP, models.ID] = Depends(backend.get_strategy),
    ):
        token, state = access_token_state
        account_id, account_email = await oauth_client.get_id_email(
            token["access_token"]
        )

        if account_email is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorCode.OAUTH_NOT_AVAILABLE_EMAIL,
            )

        try:
            data = decode_jwt(state, state_secret, [STATE_TOKEN_AUDIENCE])
        except jwt.DecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        try:
            user = await user_manager.oauth_callback(
                oauth_client.name,
                token["access_token"],
                account_id,
                account_email,
                token.get("expires_at"),
                token.get("refresh_token"),
                request,
                associate_by_email=associate_by_email,
                is_verified_by_default=is_verified_by_default,
            )
        except UserAlreadyExists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorCode.OAUTH_USER_ALREADY_EXISTS,
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorCode.LOGIN_BAD_CREDENTIALS,
            )

        # Authenticate
        response = await backend.login(strategy, user)
        await user_manager.on_after_login(user, request, response)

        _next = data.get("next")
        if _next is not None:
            return RedirectResponse(_next, headers=response.headers)
        return response

    return router


def get_auth_router(
    backend: AuthenticationBackend,
    authenticator: Authenticator,
    requires_verification: bool = False,
) -> APIRouter:
    """Generate a router with login/logout routes for an authentication backend."""
    router = APIRouter()
    get_current_user_token = authenticator.current_user_token(
        active=True, verified=requires_verification
    )

    @router.post(
        "/logout",
        name=f"auth:{backend.name}.logout",
        status_code=status.HTTP_204_NO_CONTENT,
        responses=backend.transport.get_openapi_logout_responses_success(),
    )
    async def logout(
        user_token: Tuple[models.UP, str] = Depends(get_current_user_token),
        strategy: Strategy[models.UP, models.ID] = Depends(backend.get_strategy),
    ):
        user, token = user_token
        return await backend.logout(strategy, user, token)

    return router
