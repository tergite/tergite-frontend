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
"""Updates, in MongoDB's own update operators, which every store translates

`{"$set": {"status": "done"}, "$inc": {"stats.walks": 1}}`: `$set`, `$setOnInsert` (only
when an upsert creates the record), `$inc`, `$addToSet` and `$pull` (an equal value).
"""
import enum
from numbers import Number
from typing import Any, Mapping, Type

from .exc import QueryError
from .query import is_operator_map
from .schema import Schema, resolve_field

Update = Mapping[str, Mapping[str, Any]]
UPDATE_OPERATORS = frozenset({"$set", "$setOnInsert", "$inc", "$addToSet", "$pull"})


class Returning(str, enum.Enum):
    """Which version of an updated record an update returns"""

    BEFORE = "before"
    AFTER = "after"


def check_update(schema: Type[Schema], update: Update) -> None:
    """Checks that the update uses only the dialect's operators on the schema's fields

    Raises:
        QueryError: no changes, an unknown operator, or a wrong operand
        UnknownFieldError: a field the schema does not have
    """
    if not any(update.values()):
        raise QueryError("an update needs at least one change")

    for operator, changes in update.items():
        if operator not in UPDATE_OPERATORS:
            raise QueryError(f"unknown update operator '{operator}'")
        for field, value in changes.items():
            resolve_field(schema, field)
            if operator == "$inc" and not isinstance(value, Number):
                raise QueryError(f"$inc on '{field}' takes a number")
            if operator == "$pull" and is_operator_map(value):
                raise QueryError(f"$pull on '{field}' takes a value, not operators")
