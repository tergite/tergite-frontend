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
"""What authlib needs of the app's user schema"""
from typing import List, Optional, Protocol, Set, TypeVar


class UserProtocol(Protocol):
    """A user as authlib reads it"""

    id: str
    email: str
    is_active: bool
    is_superuser: bool
    is_verified: bool
    roles: Set[str]


class OAuthAccountProtocol(Protocol):
    """An OAuth account as authlib reads it"""

    id: str
    oauth_name: str
    access_token: str
    expires_at: Optional[int]
    refresh_token: Optional[str]
    account_id: str
    account_email: str


class UserOAuthProtocol(UserProtocol, Protocol):
    """A user with the OAuth accounts they sign in with"""

    oauth_accounts: List[OAuthAccountProtocol]


UP = TypeVar("UP", bound=UserProtocol)
UOAP = TypeVar("UOAP", bound=UserOAuthProtocol)
