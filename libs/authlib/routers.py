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
"""The auth routes: OAuth sign-in through each provider, and logout"""

from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback
from httpx_oauth.oauth2 import OAuth2Token
from pydantic import BaseModel

from libs.storage import Database

from . import users
from .auth import Auth
from .cookies import clear_session_cookie, set_session_cookie
from .errors import EmailNotAvailable, InactiveUser, ProviderNotFound
from .providers import OAuthProvider
from .tokens import read_state_token, write_session_token, write_state_token

CALLBACK_ROUTE_NAME = "oauth:callback"


class OAuth2AuthorizeResponse(BaseModel):
    """The URL to send the user to, to sign in with the provider"""

    authorization_url: str


def get_oauth_router(auth: Auth, should_add_app_alias: bool = False) -> APIRouter:
    """Gets a router that signs users in through each provider, named in the paths

    It serves /{provider}/authorize, /{provider}/auto-authorize and /{provider}/callback;
    an unknown provider gets a 404.

    Args:
        auth: the app's auth, whose providers are served
        should_add_app_alias: whether the routes are also served under /app, as
            /app/{provider}/authorize

    Returns:
        the router
    """
    provider_router = APIRouter()

    @provider_router.get(
        "/{provider}/authorize",
        name="oauth:authorize",
        response_model=OAuth2AuthorizeResponse,
    )
    async def authorize(
        request: Request,
        provider: str,
        scopes: Optional[List[str]] = Query(None),
        next_url: Optional[str] = Query(None, alias="next"),
    ) -> OAuth2AuthorizeResponse:
        """Gets the URL to send the user to, to sign in through the provider

        Args:
            request: the incoming request, whose URL the provider is to call back on
            provider: the name of the provider
            scopes: the scopes to ask the provider for; default: the provider's own
            next_url: where to send the user once signed in, as `next`

        Returns:
            the provider's authorization URL

        Raises:
            404: the app has no provider of that name
        """
        authorization_url = await _get_authorization_url(
            auth, request, provider, scopes, next_url
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
        scopes: Optional[List[str]] = Query(None),
        next_url: Optional[str] = Query(None, alias="next"),
    ) -> str:
        """Redirects to the provider's authorization URL

        Args:
            request: the incoming request, whose URL the provider is to call back on
            provider: the name of the provider
            scopes: the scopes to ask the provider for; default: the provider's own
            next_url: where to send the user once signed in, as `next`

        Returns:
            the provider's authorization URL, which the response redirects to

        Raises:
            404: the app has no provider of that name
        """
        return await _get_authorization_url(auth, request, provider, scopes, next_url)

    @provider_router.get(
        "/{provider}/callback",
        name=CALLBACK_ROUTE_NAME,
        description="Logs the user in, setting the session cookie.",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            status.HTTP_307_TEMPORARY_REDIRECT: {
                "description": "Logged in; redirects to the `next` URL in the state."
            },
            status.HTTP_400_BAD_REQUEST: {
                "description": "An invalid state, no email from the provider, a user of "
                "the email who cannot be linked, or an inactive user."
            },
            status.HTTP_403_FORBIDDEN: {"description": "The email is not permitted."},
        },
    )
    async def sign_in(
        request: Request,
        provider: str,
        access_token_state: Tuple[OAuth2Token, Optional[str]] = Depends(
            _get_access_token_state(auth)
        ),
        database: Database = Depends(auth.get_database),
    ) -> Response:
        """Signs the user in from the provider's callback, setting the session cookie

        Args:
            request: the provider's callback request
            provider: the name of the provider
            access_token_state: the provider's access token, and the state sent with
                the authorization
            database: the database where the users are kept

        Returns:
            a 204, or a redirect to the state's `next` URL
        """
        token, state = access_token_state
        state_data = read_state_token(state, auth.secret)
        user = await _sign_in_user(auth, database, provider, token)
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        session_token = write_session_token(
            user, auth.secret, auth.session_lifetime_seconds
        )
        set_session_cookie(response, auth.cookie, session_token)
        if auth.on_after_login is not None:
            await auth.on_after_login(database, user)

        next_url = state_data.get("next")
        if next_url is not None:
            return RedirectResponse(next_url, headers=response.headers)
        return response

    router = APIRouter()
    router.include_router(provider_router)
    if should_add_app_alias:
        router.include_router(provider_router, prefix="/app")
    return router


def get_logout_router(auth: Auth, should_require_verified: bool = False) -> APIRouter:
    """Gets a router whose /logout clears the session cookie of an active user

    Args:
        auth: the app's auth
        should_require_verified: whether an unverified user is refused, with a 403

    Returns:
        the router
    """
    router = APIRouter()
    get_current_user = auth.get_current_user(
        should_require_active=True, should_require_verified=should_require_verified
    )

    @router.post(
        "/logout",
        name="auth:logout",
        responses={
            status.HTTP_200_OK: {
                "description": "Logged out: the session cookie is cleared.",
                "content": {"application/json": {"example": {"message": "logged out"}}},
            },
            status.HTTP_401_UNAUTHORIZED: {
                "description": "Missing token or inactive user."
            },
        },
    )
    async def logout(user: Any = Depends(get_current_user)) -> JSONResponse:
        """Logs the current user out, clearing the session cookie

        Args:
            user: the current active user

        Returns:
            the message that the user is logged out
        """
        response = JSONResponse({"message": "logged out"})
        clear_session_cookie(response, auth.cookie)
        return response

    return router


def _get_provider(auth: Auth, provider: str) -> OAuthProvider:
    """Gets the provider of the name

    Raises:
        ProviderNotFound: the app has no provider of the name
    """
    if provider not in auth.providers:
        raise ProviderNotFound()
    return auth.providers[provider]


def _get_redirect_url(auth: Auth, request: Request, provider: str) -> str:
    redirect_url = _get_provider(auth, provider).redirect_url
    if redirect_url is not None:
        return redirect_url
    return str(request.url_for(CALLBACK_ROUTE_NAME, provider=provider))


async def _get_authorization_url(
    auth: Auth,
    request: Request,
    provider: str,
    scopes: Optional[List[str]],
    next_url: Optional[str],
) -> str:
    """Gets the provider's authorization URL, with `next` kept in the state"""
    state = write_state_token(next_url, auth.secret)
    return await _get_provider(auth, provider).client.get_authorization_url(
        _get_redirect_url(auth, request, provider), state, scopes
    )


def _get_access_token_state(
    auth: Auth,
) -> Callable[..., Awaitable[Tuple[OAuth2Token, Optional[str]]]]:
    """Gets the dependency that exchanges the code a provider sent back for a token"""

    async def get_access_token_state(
        request: Request,
        provider: str,
        code: Optional[str] = None,
        code_verifier: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Tuple[OAuth2Token, Optional[str]]:
        authorize_callback = OAuth2AuthorizeCallback(
            _get_provider(auth, provider).client,
            redirect_url=_get_redirect_url(auth, request, provider),
        )
        return await authorize_callback(request, code, code_verifier, state, error)

    return get_access_token_state


async def _sign_in_user(
    auth: Auth, database: Database, provider: str, token: OAuth2Token
) -> Any:
    """Gets the active user the provider's token signs in

    Raises:
        EmailNotAvailable: the provider shares no email for the account
        InactiveUser: the user is inactive
    """
    oauth_provider = _get_provider(auth, provider)
    account_id, account_email = await oauth_provider.client.get_id_email(
        token["access_token"]
    )
    if account_email is None:
        raise EmailNotAvailable()

    account: Dict[str, Any] = {
        "access_token": token["access_token"],
        "account_id": account_id,
        "account_email": account_email,
        "expires_at": token.get("expires_at"),
        "refresh_token": token.get("refresh_token"),
    }
    user = await users.sign_in_with_oauth(
        database, auth.user_schema, provider, oauth_provider, account
    )
    if not user.is_active:
        raise InactiveUser()
    return user
