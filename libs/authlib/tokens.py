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
"""The JWTs authlib writes: session tokens, and the state passed through a provider

Their audiences are fastapi-users' own, which live cookies depend on.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

import jwt
from pydantic import SecretStr

from .errors import InvalidStateToken
from .models import UserProtocol

SESSION_AUDIENCE = ["fastapi-users:auth"]
STATE_AUDIENCE = "fastapi-users:oauth-state"
STATE_LIFETIME_SECONDS = 3600
JWT_ALGORITHM = "HS256"

SecretType = Union[str, SecretStr]


def write_session_token(
    user: UserProtocol, secret: SecretType, lifetime_seconds: Optional[int]
) -> str:
    """Writes the session token of the user, which names their id and roles"""
    data = {"sub": str(user.id), "aud": SESSION_AUDIENCE, "roles": list(user.roles)}
    return _encode_jwt(data, secret, lifetime_seconds)


def read_session_user_id(token: str, secret: SecretType) -> Optional[str]:
    """Reads the user id from a session token; None if the token is invalid or expired"""
    try:
        data = _decode_jwt(token, secret, SESSION_AUDIENCE)
    except jwt.PyJWTError:
        return None
    return data.get("sub")


def write_state_token(next_url: Optional[str], secret: SecretType) -> str:
    """Writes the state passed through a provider, which keeps where to go once in"""
    data = {"next": next_url, "aud": STATE_AUDIENCE}
    return _encode_jwt(data, secret, STATE_LIFETIME_SECONDS)


def read_state_token(token: Optional[str], secret: SecretType) -> Dict[str, Any]:
    """Reads the state a provider passed back

    Raises:
        InvalidStateToken: the state is missing, invalid or expired
    """
    if token is None:
        raise InvalidStateToken()
    try:
        return _decode_jwt(token, secret, [STATE_AUDIENCE])
    except jwt.PyJWTError as exp:
        raise InvalidStateToken() from exp


def _encode_jwt(
    data: Dict[str, Any], secret: SecretType, lifetime_seconds: Optional[int]
) -> str:
    payload = dict(data)
    if lifetime_seconds:
        payload["exp"] = datetime.now(timezone.utc) + timedelta(
            seconds=lifetime_seconds
        )
    return jwt.encode(payload, _get_secret_value(secret), algorithm=JWT_ALGORITHM)


def _decode_jwt(token: str, secret: SecretType, audience: List[str]) -> Dict[str, Any]:
    return jwt.decode(
        token, _get_secret_value(secret), audience=audience, algorithms=[JWT_ALGORITHM]
    )


def _get_secret_value(secret: SecretType) -> str:
    if isinstance(secret, SecretStr):
        return secret.get_secret_value()
    return secret
