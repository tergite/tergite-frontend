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
"""Exceptions for usage in application"""
from pydantic import ValidationError


class BaseMssException(Exception):
    def __init__(self, message: str = ""):
        self._message = message

    def __repr__(self):
        return f"{self.__class__.__name__}: {self._message}"

    def __str__(self):
        return self._message if self._message else self.__class__.__name__


class ServiceUnavailableError(BaseMssException):
    """Error when an external service is unavailable"""

    pass


class UnknownBccError(BaseMssException):
    """Exception when an unknown BCC is requested for"""


class DbValidationError(BaseMssException):
    """Exception that occurs when validation fails on a schema"""

    def __init__(self, original_exp: ValidationError):
        self._original_exp = original_exp
        self._message = f"{original_exp}"


class NotFoundError(BaseMssException):
    """Exception when a record is not found"""


class InvalidRequestIDError(BaseMssException):
    """Exception when the request id in the header is invalid"""


class InvalidWebsocketDataTypeError(BaseMssException):
    """Exception when the data type used by the websocket client is not permitted"""
