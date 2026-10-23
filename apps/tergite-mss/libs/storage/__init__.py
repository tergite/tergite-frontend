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

"""Storage that names no database technology: one Database, many backends"""
from .base.exc import (
    DuplicateKeyError,
    StorageError,
    StorageSpecError,
    UnknownFieldError,
    UnknownSchemaError,
)
from .base.ids import Id, derive_id, generate_id, is_id
from .base.query import (
    ALL,
    And,
    Contains,
    Eq,
    Filter,
    In,
    Ne,
    NotIn,
    Or,
    Page,
    Range,
    Sort,
    parse_sort,
)
from .base.schema import Schema, StorageSpec
from .base.update import AddToSet, Inc, Pull, Returning, Set, SetOnInsert, Update
from .database import Database

__all__ = [
    "ALL",
    "AddToSet",
    "And",
    "Contains",
    "Database",
    "DuplicateKeyError",
    "Eq",
    "Filter",
    "Id",
    "In",
    "Inc",
    "Ne",
    "NotIn",
    "Or",
    "Page",
    "Pull",
    "Range",
    "Returning",
    "Schema",
    "Set",
    "SetOnInsert",
    "Sort",
    "StorageError",
    "StorageSpec",
    "StorageSpecError",
    "UnknownFieldError",
    "UnknownSchemaError",
    "Update",
    "derive_id",
    "generate_id",
    "is_id",
    "parse_sort",
]
