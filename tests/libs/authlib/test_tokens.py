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
import jwt
import pytest

from libs.authlib import InvalidStateToken
from libs.authlib.tokens import (
    read_session_user_id,
    read_state_token,
    write_session_token,
    write_state_token,
)
from tests.libs.authlib.conftest import SECRET


def test_a_session_token_names_the_user_and_roles(superuser):
    token = write_session_token(superuser, SECRET, lifetime_seconds=60)

    claims = jwt.decode(
        token, SECRET, audience="fastapi-users:auth", algorithms=["HS256"]
    )
    assert claims["sub"] == superuser.id
    assert claims["roles"] == ["admin"]
    assert read_session_user_id(token, SECRET) == superuser.id


@pytest.mark.parametrize(
    "secret, lifetime_seconds",
    [("ANOTHER_SECRET", 60), (SECRET, -1)],
    ids=["another-secret", "expired"],
)
def test_an_unreadable_session_token_names_no_user(user, secret, lifetime_seconds):
    token = write_session_token(user, secret, lifetime_seconds=lifetime_seconds)

    assert read_session_user_id(token, SECRET) is None
    assert read_session_user_id("not-a-token", SECRET) is None


def test_the_state_is_for_fastapi_users_oauth_state():
    # live cookies carry fastapi-users' audiences
    state = write_state_token(None, SECRET)

    claims = jwt.decode(
        state, SECRET, audience="fastapi-users:oauth-state", algorithms=["HS256"]
    )
    assert claims["next"] is None


def test_the_state_keeps_where_to_go_next():
    state = write_state_token("https://camelot.bt/home", SECRET)

    assert read_state_token(state, SECRET)["next"] == "https://camelot.bt/home"


@pytest.mark.parametrize("state", [None, "not-a-token"])
def test_an_unreadable_state_is_invalid(state):
    with pytest.raises(InvalidStateToken):
        read_state_token(state, SECRET)
