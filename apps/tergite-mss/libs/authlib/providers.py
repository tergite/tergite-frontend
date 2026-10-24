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
"""The OAuth providers users sign in with: each one's client, rules and what it grants"""
from dataclasses import dataclass
from typing import Optional, Tuple

from httpx_oauth.oauth2 import BaseOAuth2


@dataclass(frozen=True)
class OAuthProvider:
    """One OAuth provider and the sign-ins it takes

    Attributes:
        client: the httpx-oauth client that talks to the provider
        email_regex: a pattern the start of every signing-in email must match
        roles: the roles a user gets when an account of this provider is linked to them
        redirect_url: where the provider sends users back; None for the router's own
            callback route
        should_associate_by_email: whether a first sign-in joins an existing user of the
            same email, rather than being refused
        is_verified_by_default: whether a user this provider creates starts verified
    """

    client: BaseOAuth2
    email_regex: str = ".*"
    roles: Tuple[str, ...] = ()
    redirect_url: Optional[str] = None
    should_associate_by_email: bool = False
    is_verified_by_default: bool = False
