# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""The auth behaviour that steps 5 and 7 of REFACTOR.md must keep, one test per contract row"""
import time
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

import jwt
from beanie import PydanticObjectId

import settings
from services.auth import AppToken, Project, User
from tests._utils.auth import (
    TEST_GITHUB_PROFILE,
    TEST_JWT_SECRET,
    TEST_USER_ID,
    get_auth_cookie,
)
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import (
    insert_if_not_exist,
)

_SESSION_AUDIENCE = ["fastapi-users:auth"]
_STATE_AUDIENCE = "fastapi-users:oauth-state"
_STATE_LIFETIME_SECONDS = 3600
_OAUTH_ACCOUNT_FIELDS = {
    "id",
    "oauth_name",
    "access_token",
    "expires_at",
    "refresh_token",
    "account_id",
    "account_email",
}
_APP_TOKEN_PAYLOAD = load_json_fixture("app_token_list.json")[0]


def test_session_jwt_carries_sub_audience_and_roles(
    client, github_user, cookie_oauth_state, db
):
    """The session JWT is HS256 with claims sub, aud and roles"""
    with client as client:
        response = _sign_in_with_github(client, cookie_oauth_state)

    token = _read_session_cookie(response).value
    claims = jwt.decode(
        token, TEST_JWT_SECRET, audience=_SESSION_AUDIENCE, algorithms=["HS256"]
    )
    user = db["auth_users"].find_one({"email": TEST_GITHUB_PROFILE["email"]})
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    assert claims["sub"] == str(user["_id"])
    assert claims["aud"] == _SESSION_AUDIENCE
    assert set(claims["roles"]) == set(user["roles"])


def test_session_jwt_lives_for_jwt_ttl(client, github_user, cookie_oauth_state):
    """The session JWT expires jwt_ttl seconds after sign-in"""
    with client as client:
        response = _sign_in_with_github(client, cookie_oauth_state)

    claims = jwt.decode(
        _read_session_cookie(response).value,
        TEST_JWT_SECRET,
        audience=_SESSION_AUDIENCE,
        algorithms=["HS256"],
    )
    lifetime = claims["exp"] - time.time()
    assert abs(lifetime - settings.CONFIG.auth.jwt_ttl) < 10


def test_login_cookie_flags(client, github_user, cookie_oauth_state):
    """The login cookie is named and scoped by config, http-only, secure and same-site lax"""
    with client as client:
        response = _sign_in_with_github(client, cookie_oauth_state)

    cookie = _read_session_cookie(response)
    assert cookie["domain"] == settings.CONFIG.auth.cookie_domain
    assert cookie["max-age"] == str(settings.CONFIG.auth.jwt_ttl)
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"].lower() == "lax"


def test_login_with_next_redirects_with_the_cookie(
    client, github_user, cookie_oauth_state
):
    """Sign-in with a next URL in the state redirects there, carrying the cookie"""
    with client as client:
        response = _sign_in_with_github(client, cookie_oauth_state)

    assert response.status_code == 307
    assert _read_session_cookie(response).value


def test_login_without_next_answers_204_with_the_cookie(
    client, github_user, oauth_state
):
    """Sign-in without a next URL answers 204, carrying the cookie"""
    with client as client:
        response = _sign_in_with_github(client, oauth_state)

    assert response.status_code == 204
    assert _read_session_cookie(response).value


def test_oauth_state_token(client):
    """The OAuth state is a JWT for the oauth-state audience, valid an hour, carrying next"""
    next_url = "https://example.com/after-login"

    with client as client:
        response = client.get(f"/auth/github/authorize?next={next_url}")

    authorization_url = response.json()["authorization_url"]
    state = parse_qs(urlparse(authorization_url).query)["state"][0]
    claims = jwt.decode(
        state, TEST_JWT_SECRET, audience=_STATE_AUDIENCE, algorithms=["HS256"]
    )
    assert claims["next"] == next_url
    assert abs(claims["exp"] - time.time() - _STATE_LIFETIME_SECONDS) < 10


def test_logout_requires_a_session(client):
    """POST /auth/logout without a session is unauthorized"""
    with client as client:
        response = client.post("/auth/logout")

    assert response.status_code == 401


def test_logout_requires_a_verified_user(client, db):
    """POST /auth/logout by an unverified user is forbidden"""
    user_id = _insert_user(db, email="unverified.doe@example.com", is_verified=False)

    with client as client:
        response = client.post("/auth/logout", cookies=get_auth_cookie(user_id))

    assert response.status_code == 403


def test_new_app_token_response(client, inserted_projects):
    """POST /me/tokens/ answers with the token and its type, nothing else"""
    cookies = get_auth_cookie(_APP_TOKEN_PAYLOAD["user_id"])

    with client as client:
        response = client.post("/me/tokens/", cookies=cookies, json=_APP_TOKEN_PAYLOAD)

    body = response.json()
    assert set(body) == {"access_token", "token_type"}
    assert body["token_type"] == "bearer"


def test_inactive_user_is_unauthorized(client, db):
    """A session of an inactive user is unauthorized"""
    user_id = _insert_user(db, email="inactive.doe@example.com", is_active=False)

    with client as client:
        response = client.get("/counts/notices", cookies=get_auth_cookie(user_id))

    assert response.status_code == 401


def test_malformed_session_token_is_unauthorized(client):
    """A session cookie that is not a valid JWT is unauthorized"""
    with client as client:
        response = client.get("/counts/notices", cookies={"some-cookie": "not-a-jwt"})

    assert response.status_code == 401


def test_missing_app_token_is_unauthorized(client):
    """A project route without an app token is unauthorized"""
    with client as client:
        response = client.get("/jobs/")

    assert response.status_code == 401


def test_unknown_app_token_is_unauthorized(client):
    """A project route with an app token that does not exist is unauthorized"""
    with client as client:
        response = client.get(
            "/jobs/", headers={"Authorization": "Bearer no-such-token"}
        )

    assert response.status_code == 401


def test_app_token_of_inactive_project_is_unauthorized(client, db):
    """A project route with the app token of an inactive project is unauthorized"""
    project_id = PydanticObjectId()
    insert_if_not_exist(
        db,
        Project,
        dict(
            _id=project_id,
            name="inactive-project",
            admin_id=PydanticObjectId(TEST_USER_ID),
            user_ids=[PydanticObjectId(TEST_USER_ID)],
            qpu_seconds=3600,
            is_active=False,
        ),
    )
    insert_if_not_exist(
        db,
        AppToken,
        dict(
            title="inactive-project-token",
            token="inactive-project-token",
            user_id=PydanticObjectId(TEST_USER_ID),
            project_id=project_id,
            lifespan_seconds=3600,
        ),
    )

    with client as client:
        response = client.get(
            "/jobs/", headers={"Authorization": "Bearer inactive-project-token"}
        )

    assert response.status_code == 401


def test_malformed_project_id_in_path_is_not_found(
    client, user_jwt_cookie, admin_jwt_cookie
):
    """A project id that is not an id answers 404, not 422"""
    with client as client:
        mine = client.get("/me/projects/not-an-id", cookies=user_jwt_cookie)
        admin = client.get("/admin/projects/not-an-id", cookies=admin_jwt_cookie)

    assert mine.status_code == 404
    assert admin.status_code == 404


def test_oauth_accounts_keep_their_fields(client, github_user, cookie_oauth_state, db):
    """A signed-in user's oauth_accounts entries keep fastapi-users' seven fields"""
    with client as client:
        _sign_in_with_github(client, cookie_oauth_state)

    user = db["auth_users"].find_one({"email": TEST_GITHUB_PROFILE["email"]})
    assert [set(account) for account in user["oauth_accounts"]] == [
        _OAUTH_ACCOUNT_FIELDS
    ]


def _sign_in_with_github(client, state: str):
    return client.get(
        f"/auth/github/callback?code=test&state={state}", follow_redirects=False
    )


def _read_session_cookie(response):
    cookies = SimpleCookie()
    cookies.load(response.headers["set-cookie"])
    return cookies[settings.CONFIG.auth.cookie_name]


def _insert_user(
    db, email: str, is_active: bool = True, is_verified: bool = True
) -> str:
    user_id = PydanticObjectId()
    insert_if_not_exist(
        db,
        User,
        dict(
            _id=user_id,
            email=email,
            hashed_password="unused",
            is_active=is_active,
            is_verified=is_verified,
            roles=["user"],
        ),
    )
    return str(user_id)
