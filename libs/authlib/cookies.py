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
"""The session cookie: how it is set at login and cleared at logout"""
from dataclasses import dataclass
from typing import Literal, Optional

from fastapi import Response


@dataclass(frozen=True)
class SessionCookie:
    """The session cookie's name and attributes

    Attributes:
        name: the cookie's name
        max_age: the seconds it lives; None for the browser session
        path: the path it is sent to
        domain: the domain it is sent to; None for the host that set it
        is_secure: whether it is sent over HTTPS only
        is_http_only: whether scripts are kept from reading it
        same_site: when it is sent with cross-site requests
    """

    name: str
    max_age: Optional[int] = None
    path: str = "/"
    domain: Optional[str] = None
    is_secure: bool = True
    is_http_only: bool = True
    same_site: Literal["lax", "strict", "none"] = "lax"


def set_session_cookie(response: Response, cookie: SessionCookie, token: str) -> None:
    response.set_cookie(
        cookie.name,
        token,
        max_age=cookie.max_age,
        path=cookie.path,
        domain=cookie.domain,
        secure=cookie.is_secure,
        httponly=cookie.is_http_only,
        samesite=cookie.same_site,
    )


def clear_session_cookie(response: Response, cookie: SessionCookie) -> None:
    response.set_cookie(
        cookie.name,
        "",
        max_age=0,
        path=cookie.path,
        domain=cookie.domain,
        secure=cookie.is_secure,
        httponly=cookie.is_http_only,
        samesite=cookie.same_site,
    )
