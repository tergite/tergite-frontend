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
list field that holds it, and `$elemMatch` matches a list of models holding one element that
meets every condition: `{"accounts": {"$elemMatch": {"name": "github", "id": "42"}}}`.
`$regex` takes only escaped text with `$options: "i"`, a case-insensitive substring:
`{"email": {"$regex": re.escape(text), "$options": "i"}}`. A sort lists fields; a leading
'-' sorts descending.
"""

import re
from typing import Any, Iterator, List, Mapping, Optional, Sequence, Tuple, Type

from .exc import QueryError
from .schema import Schema, is_model_list, resolve_field

Filter = Mapping[str, Any]
FIELD_OPERATORS = frozenset(
    {"$eq", "$ne", "$in", "$nin", "$gt", "$gte", "$lt", "$lte", "$regex", "$options"}
)
LIST_OPERATORS = frozenset({"$in", "$nin"})
LOGICAL_OPERATORS = frozenset({"$and", "$or"})
ELEMENT_MATCH = "$elemMatch"


def check_filter(schema: Type[Schema], query_filter: Optional[Filter]) -> None:
    """Checks that the filter names only the schema's fields and the dialect's operators

    Args:
        schema: the schema of the records filtered
        query_filter: the filter; None matches every record

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
        elif is_operator_map(condition) and ELEMENT_MATCH in condition:
            _check_element_match(schema, field, condition)
        elif is_model_list(resolve_field(schema, field)):
            raise QueryError(f"list of models '{field}' is matched with $elemMatch")
        else:
            _check_condition(field, condition)


def check_sort(schema: Type[Schema], sort: Sequence[str]) -> None:
    """Checks that the sort names only the schema's fields

    Args:
        schema: the schema of the records sorted
        sort: the fields to sort by; a leading '-' sorts descending

    Raises:
        UnknownFieldError: a field the schema does not have
    """
    for field in sort:
        resolve_field(schema, field.lstrip("-"))


def extract_fields(query_filter: Optional[Filter]) -> Iterator[str]:
    """Yields every field the filter names, nested filters included

    Args:
        query_filter: the filter; None names no field

    Yields:
        each field the filter names, as named
    """
    for field, condition in (query_filter or {}).items():
        if field in LOGICAL_OPERATORS:
            for item in condition:
                yield from extract_fields(item)
        else:
            yield field


def parse_sort(sort: Sequence[str]) -> List[Tuple[str, bool]]:
    """Parses sort fields such as ("-created_at", "name") into (field, is_descending) pairs

    Args:
        sort: the fields to sort by; a leading '-' sorts descending

    Returns:
        a (field, is_descending) pair per field
    """
    return [(field.lstrip("-"), field.startswith("-")) for field in sort]


def get_searched_text(escaped_text: str) -> str:
    """Gets the text a `$regex` searches for, from its escaped form

    Args:
        escaped_text: the `$regex` operand, escaped as `re.escape` does

    Returns:
        the unescaped text
    """
    return re.sub(r"\\(.)", r"\1", escaped_text, flags=re.DOTALL)


def is_operator_map(condition: Any) -> bool:
    """Whether the condition is a map of field operators rather than a value to equal

    Args:
        condition: a field's condition in a filter

    Returns:
        True if any of the condition's keys is an operator, such as `$in`
    """
    return isinstance(condition, Mapping) and any(
        str(key).startswith("$") for key in condition
    )


def _check_condition(field: str, condition: Any) -> None:
    if not is_operator_map(condition):
        return
    if "$regex" in condition or "$options" in condition:
        _check_text_search(field, condition)
    for operator, operand in condition.items():
        if operator not in FIELD_OPERATORS:
            raise QueryError(f"unknown operator '{operator}' on '{field}'")
        if operator in LIST_OPERATORS and not isinstance(operand, (list, tuple, set)):
            raise QueryError(f"{operator} on '{field}' takes a list")


def _check_element_match(schema: Type[Schema], field: str, condition: Any) -> None:
    """Checks a $elemMatch: alone on a list of models, with conditions on their fields

    Raises:
        QueryError: $elemMatch beside other operators, on another field, or without a filter
        UnknownFieldError: a field the elements do not have
    """
    if set(condition) != {ELEMENT_MATCH}:
        raise QueryError(f"$elemMatch on '{field}' takes no other operators")
    if not is_model_list(resolve_field(schema, field)):
        raise QueryError(f"$elemMatch needs a list of models, which '{field}' is not")
    element_filter = condition[ELEMENT_MATCH]
    if not isinstance(element_filter, Mapping) or len(element_filter) == 0:
        raise QueryError(f"$elemMatch on '{field}' takes a non-empty filter")
    for element_field, element_condition in element_filter.items():
        resolve_field(schema, f"{field}.{element_field}")
        _check_condition(f"{field}.{element_field}", element_condition)


def _check_text_search(field: str, condition: Mapping[str, Any]) -> None:
    """Checks a $regex: escaped text, case-insensitive, beside no other operator

    Raises:
        QueryError: other operators, other options, or a pattern that is not escaped text
    """
    if set(condition) != {"$regex", "$options"} or condition["$options"] != "i":
        raise QueryError(f"$regex on '{field}' takes only $options 'i'")
    pattern = condition["$regex"]
    if not isinstance(pattern, str) or re.escape(get_searched_text(pattern)) != pattern:
        raise QueryError(f"$regex on '{field}' takes escaped text, not a pattern")
