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


class ForbiddenError(BaseMssException):
    """Exception when a request is forbidden"""


class ConflictError(BaseMssException):
    """Exception when a request conflicts with the current state of a resource"""


class TooManyRequestsError(BaseMssException):
    """Exception when a client has exceeded a rate limit"""


class UnauthorizedError(BaseMssException):
    """Exception when a request carries no valid credentials"""


class InvalidInputError(BaseMssException):
    """Exception when a client sends a value that cannot be used"""


class TooManyListQueryParams(InvalidInputError):
    """Exception when a list query param has more items than a mongodb $in handles well

    https://www.mongodb.com/docs/manual/reference/operator/query/in/#syntax
    """

    def __init__(self, query_param: str, expected: int, got: int):
        super().__init__(
            f"too many items passed to query {query_param}; expected {expected}, got {got}"
        )


class BccHttpError(BaseMssException):
    """Exception when a BCC answers with an HTTP error"""

    def __init__(self, status_code: int, message: str = ""):
        super().__init__(message)
        self.status_code = status_code


class DatabaseError(BaseMssException):
    """Exception when the database fails to carry out an operation"""
