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
from fastapi import Response

from libs.authlib import SessionCookie
from libs.authlib.cookies import clear_session_cookie, set_session_cookie


def test_the_session_cookie_is_set_with_its_attributes():
    response = Response()
    cookie = SessionCookie(name="session", max_age=60, domain="camelot.bt")

    set_session_cookie(response, cookie, "TOKEN")

    header = response.headers["set-cookie"]
    assert header.startswith("session=TOKEN;")
    for attribute in ("Domain=camelot.bt", "HttpOnly", "Max-Age=60", "SameSite=lax"):
        assert attribute in header
    assert "Secure" in header


def test_the_session_cookie_is_cleared():
    response = Response()

    clear_session_cookie(response, SessionCookie(name="session"))

    assert 'session="";' in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
