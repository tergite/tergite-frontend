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
"""The dependencies that get a request's user from its session token"""

from typing import Optional

import pytest
from fastapi import Depends, FastAPI, status

from libs.authlib import add_exception_handlers, write_session_token
from tests.libs.authlib.conftest import COOKIE_NAME, SECRET, UserModel


@pytest.fixture
async def test_auth_client(auth, get_test_client):
    app = FastAPI()
    add_exception_handlers(app)

    @app.get("/user")
    def read_user(user: UserModel = Depends(auth.get_current_user())):
        return user.id

    @app.get("/optional-user")
    def read_optional_user(
        user: Optional[UserModel] = Depends(auth.get_current_user(is_optional=True)),
    ):
        return None if user is None else user.id

    @app.get("/active-user")
    def read_active_user(
        user: UserModel = Depends(auth.get_current_user(should_require_active=True)),
    ):
        return user.id

    @app.get("/verified-user")
    def read_verified_user(
        user: UserModel = Depends(auth.get_current_user(should_require_verified=True)),
    ):
        return user.id

    @app.get("/superuser")
    def read_superuser(
        user: UserModel = Depends(auth.get_current_user(should_require_superuser=True)),
    ):
        return user.id

    @app.get("/admin")
    def read_admin(
        user: UserModel = Depends(auth.get_current_user(roles=("admin",))),
    ):
        return user.id

    @app.get("/user-id")
    def read_user_id(user_id: str = Depends(auth.get_current_user_id())):
        return user_id

    @app.get("/optional-user-id")
    def read_optional_user_id(
        user_id: Optional[str] = Depends(auth.get_current_user_id(is_optional=True)),
    ):
        return user_id

    async for client in get_test_client(app):
        yield client


@pytest.mark.parametrize("path", ["/user", "/user-id"])
@pytest.mark.parametrize(
    "is_in_header, is_in_cookie, is_bad_header",
    [(True, False, False), (False, True, False), (False, True, True)],
    ids=["bearer", "cookie", "bad-bearer-then-cookie"],
)
async def test_a_session_token_in_the_header_or_cookie_names_the_user(
    test_auth_client, user, path, is_in_header, is_in_cookie, is_bad_header
):
    token = _get_token(user)
    headers = {"Authorization": f"Bearer {token}"} if is_in_header else {}
    if is_bad_header:
        headers = {"Authorization": "Bearer not-a-token"}
    if is_in_cookie:
        test_auth_client.cookies.set(COOKIE_NAME, token)

    response = await test_auth_client.get(path, headers=headers)

    assert response.json() == user.id


@pytest.mark.parametrize("path", ["/user", "/user-id"])
async def test_no_session_is_unauthorized(test_auth_client, path):
    response = await test_auth_client.get(
        path, headers={"Authorization": "Bearer not-a-token"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.parametrize("path", ["/optional-user", "/optional-user-id"])
async def test_an_optional_user_is_none_without_a_session(test_auth_client, path):
    response = await test_auth_client.get(path)

    assert response.json() is None


async def test_a_token_naming_no_stored_user_is_unauthorized(test_auth_client):
    token = _get_token(UserModel(id="0" * 24, email="ghost@camelot.bt"))

    response = await test_auth_client.get(
        "/user", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(
    "path, user_fixture, expected_status",
    [
        ("/active-user", "inactive_user", status.HTTP_401_UNAUTHORIZED),
        ("/verified-user", "unverified_user", status.HTTP_403_FORBIDDEN),
        ("/superuser", "user", status.HTTP_403_FORBIDDEN),
        ("/admin", "user", status.HTTP_403_FORBIDDEN),
        ("/superuser", "superuser", status.HTTP_200_OK),
        ("/admin", "superuser", status.HTTP_200_OK),
    ],
)
async def test_a_user_lacking_what_the_route_requires_is_refused(
    test_auth_client, request, path, user_fixture, expected_status
):
    token = _get_token(request.getfixturevalue(user_fixture))

    response = await test_auth_client.get(
        path, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == expected_status


def _get_token(user: UserModel) -> str:
    return write_session_token(user, SECRET, lifetime_seconds=60)
