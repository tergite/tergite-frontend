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
"""What each OAuth provider's sign-ins must meet, and what they grant"""
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ProviderRules:
    """The rules of one provider's sign-ins

    Attributes:
        email_regex: a pattern the start of every signing-in email must match
        roles: the roles a user gets when an account of this provider is linked to them
    """

    email_regex: str
    roles: Tuple[str, ...] = ()
