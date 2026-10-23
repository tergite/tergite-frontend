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

"""Errors of the storage layer"""


class StorageError(Exception):
    """The base of every storage error"""


class UnknownSchemaError(StorageError):
    """A schema the Database was not created with"""


class UnknownFieldError(StorageError):
    """A field name that the schema does not have"""


class StorageSpecError(StorageError):
    """A __storage__ that does not fit its schema"""


class DuplicateKeyError(StorageError):
    """A write that would break a unique field"""
