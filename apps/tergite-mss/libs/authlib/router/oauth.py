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
"""The OAuth routes of every provider: /{provider}/authorize, auto-authorize and callback"""
from typing import Dict, List, Mapping, Optional, Tuple

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback
from httpx_oauth.oauth2 import OAuth2Token
from pydantic import BaseModel

from libs.authlib import models
from libs.authlib.authentication import AuthenticationBackend, Strategy
from libs.authlib.exceptions import UserAlreadyExists
from libs.authlib.jwt import SecretType, decode_jwt, generate_jwt
from libs.authlib.manager import BaseUserManager, UserManagerDependency
from libs.authlib.providers import OAuthProvider
from libs.authlib.router.common import ErrorCode, ErrorModel

STATE_TOKEN_AUDIENCE = "fastapi-users:oauth-state"
CALLBACK_ROUTE_NAME = "oauth:callback"


class OAuth2AuthorizeResponse(BaseModel):
    authorization_url: str


def generate_state_token(
    data: dict[str, str], secret: SecretType, lifetime_seconds: int = 3600
) -> str:
    data["aud"] = STATE_TOKEN_AUDIENCE
    return generate_jwt(data, secret, lifetime_seconds)


def get_oauth_router(
    providers: Mapping[str, OAuthProvider],
    backend: AuthenticationBackend[models.UP, models.ID],
    get_user_manager: UserManagerDependency[models.UP, models.ID],
    state_secret: SecretType,
    should_add_app_alias: bool = False,
) -> APIRouter:
    """Gets a router with the OAuth routes of the providers, named in each path

    An unknown provider gets a 404.

    Args:
        providers: the providers by name, as their paths name them
        backend: the authentication backend that logs users in
        get_user_manager: the user manager dependency
        state_secret: the secret of the state token passed through the provider
        should_add_app_alias: whether the routes are also served under /app, as
            /app/{provider}/authorize
    """
    provider_router = APIRouter()

    def get_provider(provider: str) -> OAuthProvider:
        if provider not in providers:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return providers[provider]

    def get_redirect_url(request: Request, provider: str) -> str:
        redirect_url = get_provider(provider).redirect_url
        if redirect_url is not None:
            return redirect_url
        return str(request.url_for(CALLBACK_ROUTE_NAME, provider=provider))

    async def get_authorization_url(
        request: Request,
        provider: str,
        scopes: Optional[List[str]],
        next_url: Optional[str],
    ) -> str:
        """Gets the provider's authorization URL, with `next` kept in the state"""
        state_data: Dict[str, Optional[str]] = {"next": next_url}
        state = generate_state_token(state_data, state_secret)
        return await get_provider(provider).client.get_authorization_url(
            get_redirect_url(request, provider), state, scopes
        )

    async def get_access_token_state(
        request: Request,
        provider: str,
        code: Optional[str] = None,
        code_verifier: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Tuple[OAuth2Token, Optional[str]]:
        """Exchanges the code the provider sent back for an access token"""
        authorize_callback = OAuth2AuthorizeCallback(
            get_provider(provider).client,
            redirect_url=get_redirect_url(request, provider),
        )
        return await authorize_callback(request, code, code_verifier, state, error)

    @provider_router.get(
        "/{provider}/authorize",
        name="oauth:authorize",
        response_model=OAuth2AuthorizeResponse,
    )
    async def authorize(
        request: Request,
        provider: str,
        scopes: List[str] = Query(None),
        next_url: Optional[str] = Query(None, alias="next"),
    ) -> OAuth2AuthorizeResponse:
        authorization_url = await get_authorization_url(
            request, provider, scopes, next_url
        )
        return OAuth2AuthorizeResponse(authorization_url=authorization_url)

    @provider_router.get(
        "/{provider}/auto-authorize",
        name="oauth:auto-authorize",
        response_class=RedirectResponse,
    )
    async def authorize_by_redirect(
        request: Request,
        provider: str,
        scopes: List[str] = Query(None),
        next_url: Optional[str] = Query(None, alias="next"),
    ) -> str:
        """Redirects to the provider's authorization URL"""
        return await get_authorization_url(request, provider, scopes, next_url)

    @provider_router.get(
        "/{provider}/callback",
        name=CALLBACK_ROUTE_NAME,
        description="The response varies based on the authentication backend used.",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            **backend.transport.get_openapi_login_responses_success(),
            status.HTTP_307_TEMPORARY_REDIRECT: {
                "description": "Logged in; redirects to the `next` URL in the state."
            },
            status.HTTP_400_BAD_REQUEST: {
                "model": ErrorModel,
                "content": {
                    "application/json": {
                        "examples": {
                            "INVALID_STATE_TOKEN": {
                                "summary": "Invalid state token.",
                                "value": None,
                            },
                            ErrorCode.LOGIN_BAD_CREDENTIALS: {
                                "summary": "User is inactive.",
                                "value": {"detail": ErrorCode.LOGIN_BAD_CREDENTIALS},
                            },
                        }
                    }
                },
            },
        },
    )
    async def callback(
        request: Request,
        provider: str,
        access_token_state: Tuple[OAuth2Token, Optional[str]] = Depends(
            get_access_token_state
        ),
        user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
        strategy: Strategy[models.UP, models.ID] = Depends(backend.get_strategy),
    ):
        oauth_provider = get_provider(provider)
        token, state = access_token_state
        account_id, account_email = await oauth_provider.client.get_id_email(
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
                provider,
                token["access_token"],
                account_id,
                account_email,
                token.get("expires_at"),
                token.get("refresh_token"),
                request,
                associate_by_email=oauth_provider.should_associate_by_email,
                is_verified_by_default=oauth_provider.is_verified_by_default,
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

        next_url = data.get("next")
        if next_url is not None:
            return RedirectResponse(next_url, headers=response.headers)
        return response

    router = APIRouter()
    router.include_router(provider_router)
    if should_add_app_alias:
        router.include_router(provider_router, prefix="/app")
    return router
