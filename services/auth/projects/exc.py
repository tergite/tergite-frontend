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

"""Exceptions for auth with respect to the projects submodule"""

from enum import Enum

from utils.exc import ConflictError, NotFoundError


class ExtendedErrorCode(str, Enum):
    """The error codes, beyond the standard ones, for project errors"""

    PROJECT_ALREADY_EXISTS = "PROJECT_ALREADY_EXISTS"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    BAD_CREDENTIALS = "BAD_CREDENTIALS"
    UPDATE_PROJECT_EXT_ID_ALREADY_EXISTS = "UPDATE_PROJECT_EXT_ID_ALREADY_EXISTS"


class ProjectNotExists(NotFoundError):
    """No project has the given id"""

    pass


class ProjectExists(ConflictError):
    """A project of the same name already exists"""

    pass
