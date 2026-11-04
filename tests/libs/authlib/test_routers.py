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
"""The OAuth sign-in and logout routes"""

import dataclasses
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status

from libs.authlib import (
    add_exception_handlers,
    get_logout_router,
    get_oauth_router,
    read_session_user_id,
    write_session_token,
)
from libs.authlib.tokens import read_state_token, write_state_token
from tests.libs.authlib.conftest import COOKIE_NAME, SECRET


@pytest.fixture
async def test_app_client(auth, get_test_client):
    app = FastAPI()
    add_exception_handlers(app)
    app.include_router(
        get_oauth_router(auth, should_add_app_alias=True), prefix="/auth"
    )
    app.include_router(
        get_logout_router(auth, should_require_verified=True), prefix="/auth"
    )

    async for client in get_test_client(app):
        yield client


@pytest.fixture
def provider_account(mocker, oauth_client):
    """The provider exchanges any code for a token of the account it is given"""

    def _provider_account(account_id: str, email: str) -> AsyncMock:
        mocker.patch.object(
            oauth_client,
            "get_access_token",
            new_callable=AsyncMock,
            return_value={"access_token": "TOKEN", "expires_at": 1579179542},
        )
        return mocker.patch.object(
            oauth_client,
            "get_id_email",
            new_callable=AsyncMock,
            return_value=(account_id, email),
        )

    return _provider_account


@pytest.mark.parametrize("path", ["/auth/service1", "/auth/app/service1"])
async def test_authorize_gives_the_provider_url_with_next_in_the_state(
    mocker, test_app_client, oauth_client, path
):
    get_authorization_url = mocker.patch.object(
        oauth_client,
        "get_authorization_url",
        new_callable=AsyncMock,
        return_value="https://camelot.bt/login",
    )

    response = await test_app_client.get(
        f"{path}/authorize", params={"next": "https://camelot.bt/home"}
    )

    redirect_url, state, _ = get_authorization_url.call_args.args
    assert response.json() == {"authorization_url": "https://camelot.bt/login"}
    assert redirect_url == "http://app.io/auth/service1/callback"
    assert read_state_token(state, SECRET)["next"] == "https://camelot.bt/home"


async def test_auto_authorize_redirects_to_the_provider(
    mocker, test_app_client, oauth_client
):
    mocker.patch.object(
        oauth_client,
        "get_authorization_url",
        new_callable=AsyncMock,
        return_value="https://camelot.bt/login",
    )

    response = await test_app_client.get("/auth/service1/auto-authorize")

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == "https://camelot.bt/login"


async def test_an_unknown_provider_is_not_found(test_app_client):
    response = await test_app_client.get("/auth/service9/authorize")

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_the_callback_logs_the_user_in_with_a_session_cookie(
    test_app_client, provider_account, user, logged_in_users
):
    provider_account("user_oauth1", user.email)

    response = await test_app_client.get(
        "/auth/service1/callback",
        params={"code": "CODE", "state": write_state_token(None, SECRET)},
    )

    session_token = response.cookies[COOKIE_NAME]
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert read_session_user_id(session_token, SECRET) == user.id
    assert [logged_in.id for logged_in in logged_in_users] == [user.id]


async def test_the_callback_redirects_to_next_with_the_session_cookie(
    test_app_client, provider_account, user
):
    provider_account("user_oauth1", user.email)
    state = write_state_token("https://camelot.bt/home", SECRET)

    response = await test_app_client.get(
        "/auth/service1/callback", params={"code": "CODE", "state": state}
    )

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == "https://camelot.bt/home"
    assert COOKIE_NAME in response.cookies


async def test_the_callback_exchanges_the_code_at_the_provider_redirect_url(
    auth, test_app_client, provider_account, oauth_client, user, provider
):
    auth.providers["service1"] = dataclasses.replace(
        provider, redirect_url="https://camelot.bt/callback"
    )
    provider_account("user_oauth1", user.email)

    await test_app_client.get(
        "/auth/service1/callback",
        params={"code": "CODE", "state": write_state_token(None, SECRET)},
    )

    oauth_client.get_access_token.assert_called_once_with(
        "CODE", "https://camelot.bt/callback", None
    )


@pytest.mark.parametrize(
    "account_id, email, state_secret, expected_status, expected_detail",
    [
        ("user_oauth1", "king.arthur@camelot.bt", "WRONG", 400, "Bad Request"),
        ("user_oauth1", None, SECRET, 400, "OAUTH_NOT_AVAILABLE_EMAIL"),
        (
            "merlin_oauth1",
            "merlin@camelot.bt",
            SECRET,
            400,
            "OAUTH_USER_ALREADY_EXISTS",
        ),
        (
            "inactive_oauth1",
            "percival@camelot.bt",
            SECRET,
            400,
            "LOGIN_BAD_CREDENTIALS",
        ),
        ("mordred_oauth1", "mordred@orkney.bt", SECRET, 403, "user not permitted"),
    ],
    ids=["bad-state", "no-email", "email-taken", "inactive", "email-not-permitted"],
)
async def test_the_callback_refuses_what_cannot_sign_in(
    test_app_client,
    provider_account,
    logged_in_users,
    account_id,
    email,
    state_secret,
    expected_status,
    expected_detail,
):
    provider_account(account_id, email)
    state = write_state_token(None, state_secret)

    response = await test_app_client.get(
        "/auth/service1/callback", params={"code": "CODE", "state": state}
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert logged_in_users == []


async def test_logout_clears_the_session_cookie(test_app_client, user):
    test_app_client.cookies.set(COOKIE_NAME, _get_token(user))

    response = await test_app_client.post("/auth/logout")

    assert response.json() == {"message": "logged out"}
    assert "Max-Age=0" in response.headers["set-cookie"]


@pytest.mark.parametrize(
    "user_fixture, expected_status",
    [(None, 401), ("inactive_user", 401), ("unverified_user", 403)],
)
async def test_logout_needs_an_active_verified_user(
    test_app_client, request, user_fixture, expected_status
):
    if user_fixture is not None:
        token = _get_token(request.getfixturevalue(user_fixture))
        test_app_client.cookies.set(COOKIE_NAME, token)

    response = await test_app_client.post("/auth/logout")

    assert response.status_code == expected_status


def _get_token(user) -> str:
    return write_session_token(user, SECRET, lifetime_seconds=60)
