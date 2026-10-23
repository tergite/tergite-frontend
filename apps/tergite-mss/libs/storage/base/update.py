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

"""Changes to a record: plain structs that each store translates for its database"""
import enum
from dataclasses import dataclass
from typing import Any, Union


@dataclass(frozen=True)
class Set:
    field: str
    value: Any


@dataclass(frozen=True)
class SetOnInsert:
    """Sets the field only when an upsert creates the record"""

    field: str
    value: Any


@dataclass(frozen=True)
class Inc:
    field: str
    amount: float


@dataclass(frozen=True)
class AddToSet:
    """Adds the value to a list field unless the list holds it already"""

    field: str
    value: Any


@dataclass(frozen=True)
class Pull:
    """Removes every occurrence of the value from a list field"""

    field: str
    value: Any


Update = Union[Set, SetOnInsert, Inc, AddToSet, Pull]


class Returning(str, enum.Enum):
    """Which version of an updated record an update returns"""

    BEFORE = "before"
    AFTER = "after"
