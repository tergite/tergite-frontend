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

"""Filters, sorts and pages: plain structs that each store translates for its database

Fields are named as on the schema, dotted for nested objects (`timestamps.started`). On a list
field, `Eq` and `In` match a list holding the value, as a membership test.
"""
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple, Union


@dataclass(frozen=True)
class Eq:
    field: str
    value: Any


@dataclass(frozen=True)
class Ne:
    field: str
    value: Any


@dataclass(frozen=True)
class In:
    field: str
    values: Sequence[Any]


@dataclass(frozen=True)
class NotIn:
    field: str
    values: Sequence[Any]


@dataclass(frozen=True)
class Range:
    """Matches values within the given bounds; a bound left as None is open"""

    field: str
    gt: Any = None
    gte: Any = None
    lt: Any = None
    lte: Any = None


@dataclass(frozen=True)
class Contains:
    """Matches string values that contain the text"""

    field: str
    text: str
    is_case_sensitive: bool = True


@dataclass(frozen=True, init=False)
class And:
    filters: Tuple["Filter", ...]

    def __init__(self, *filters: "Filter"):
        object.__setattr__(self, "filters", filters)


@dataclass(frozen=True, init=False)
class Or:
    filters: Tuple["Filter", ...]

    def __init__(self, *filters: "Filter"):
        object.__setattr__(self, "filters", filters)


Filter = Union[Eq, Ne, In, NotIn, Range, Contains, And, Or]
ALL = And()
"""The filter every record matches"""


@dataclass(frozen=True)
class Sort:
    field: str
    is_descending: bool = False


@dataclass(frozen=True)
class Page:
    skip: int = 0
    limit: Optional[int] = None
