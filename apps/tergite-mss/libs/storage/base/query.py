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
"""Filters and sorts, in MongoDB's own query dialect, which every store translates

A filter maps schema fields, dotted for nested objects (`timestamps.started`), to a value or
to field operators, and may hold `$and` and `$or` lists of filters:
`{"id": pk, "user_id": {"$in": [user_id, None]}}`. As in MongoDB, a value or `$in` matches a
list field that holds it. A sort lists fields; a leading '-' sorts descending.
"""
from typing import Any, Iterator, List, Mapping, Optional, Sequence, Tuple, Type

from .exc import QueryError
from .schema import Schema, resolve_field

Filter = Mapping[str, Any]
FIELD_OPERATORS = frozenset({"$eq", "$ne", "$in", "$nin", "$gt", "$gte", "$lt", "$lte"})
LIST_OPERATORS = frozenset({"$in", "$nin"})
LOGICAL_OPERATORS = frozenset({"$and", "$or"})


def check_filter(schema: Type[Schema], query_filter: Optional[Filter]) -> None:
    """Checks that the filter names only the schema's fields and the dialect's operators

    Raises:
        QueryError: an operator the dialect does not have, or one given the wrong operand
        UnknownFieldError: a field the schema does not have
    """
    for field, condition in (query_filter or {}).items():
        if field in LOGICAL_OPERATORS:
            if not isinstance(condition, (list, tuple)) or len(condition) == 0:
                raise QueryError(f"{field} takes a non-empty list of filters")
            for item in condition:
                check_filter(schema, item)
        elif field.startswith("$"):
            raise QueryError(f"unknown operator '{field}'")
        else:
            resolve_field(schema, field)
            _check_condition(field, condition)


def check_sort(schema: Type[Schema], sort: Sequence[str]) -> None:
    for field in sort:
        resolve_field(schema, field.lstrip("-"))


def extract_fields(query_filter: Optional[Filter]) -> Iterator[str]:
    """Yields every field the filter names, nested filters included"""
    for field, condition in (query_filter or {}).items():
        if field in LOGICAL_OPERATORS:
            for item in condition:
                yield from extract_fields(item)
        else:
            yield field


def parse_sort(sort: Sequence[str]) -> List[Tuple[str, bool]]:
    """Parses sort fields such as ("-created_at", "name") into (field, is_descending) pairs"""
    return [(field.lstrip("-"), field.startswith("-")) for field in sort]


def is_operator_map(condition: Any) -> bool:
    """Whether the condition is a map of field operators rather than a value to equal"""
    return isinstance(condition, Mapping) and any(
        str(key).startswith("$") for key in condition
    )


def _check_condition(field: str, condition: Any) -> None:
    if not is_operator_map(condition):
        return
    for operator, operand in condition.items():
        if operator not in FIELD_OPERATORS:
            raise QueryError(f"unknown operator '{operator}' on '{field}'")
        if operator in LIST_OPERATORS and not isinstance(operand, (list, tuple, set)):
            raise QueryError(f"{operator} on '{field}' takes a list")
