# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Exceptions for auth with respect to the app_tokens submodule"""
from enum import Enum

from utils.exc import ForbiddenError


class ExtendedErrorCode(str, Enum):
    """The error codes, beyond the standard ones, for app token errors"""

    BAD_CREDENTIALS = "BAD_CREDENTIALS"


class AppTokenNotFound(ForbiddenError):
    """The user has no such app token, or it has expired"""

    def __init__(self, message: str = "app token does not exist or is expired."):
        super().__init__(message)
