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

from typing import Optional


class BaseMssException(Exception):
    """The base of MSS's own errors, shown by their message, or class name if none"""

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


class NotFoundError(BaseMssException):
    """Exception when a record is not found"""


class ForbiddenError(BaseMssException):
    """Exception when a request is forbidden"""


class ConflictError(BaseMssException):
    """Exception when a request conflicts with the current state of a resource"""


class JobAlreadyEndedError(ConflictError):
    """Exception when an update would change the status of a job that has ended"""


class UnauthorizedError(BaseMssException):
    """Exception when a request carries no valid credentials"""


class InvalidInputError(BaseMssException):
    """Exception when a client sends a value that cannot be used"""


class InvalidCircuitError(InvalidInputError):
    """A circuit a backend cannot run, and where in the submission and its text the problem is

    Attributes:
        index: the circuit's place in the submission
        message: what is wrong, as the backend words it
        line: the line, from 1, if known
        column: the column, from 1, if known
    """

    def __init__(
        self,
        index: int,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
    ):
        super().__init__(message)
        self.index = index
        self.message = message
        self.line = line
        self.column = column


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
