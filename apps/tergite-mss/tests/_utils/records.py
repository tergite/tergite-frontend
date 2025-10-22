# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
# (C) Copyright Chalmers Next Labs AB 2024, 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Test utilities for handling records"""
import copy
from datetime import datetime, timedelta, timezone
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    TypeVar,
)

from tests._utils.date_time import get_timestamp_str

T = TypeVar("T")


def pop_field(records: List[Dict[str, Any]], field: str) -> List[Any]:
    """Pops a given field from the list of records and returns the list of popped values.

    Note that it mutates the items in the record list

    Args:
        records: the list of records
        field: the key to pop from the records

    Returns:
        a new list containing the values of the given field in the original records
    """
    results = []
    for item in records:
        results.append(item.pop(field))

    return results


def prune(
    record: Dict[str, Any], fields: List[str]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Removes given fields from a record and returns the record and the dict of popped values.

    This does not mutate the record

    Args:
        record: the dictionary to prune
        fields: the key to pop from the records

    Returns:
        a new record and the dict of popped values
    """
    new_record = copy.deepcopy(record)
    popped_values = {k: new_record.pop(k, None) for k in fields}

    return new_record, popped_values


def order_by(
    data: List[Dict[str, Any]], field: str, is_descending: bool = False
) -> List[Dict[str, Any]]:
    """Orders the data by given field

    Args:
        data: the list of records to sort
        field: the field to order by
        is_descending: whether to sort in descending order

    Returns:
        the ordered list of records
    """
    return sorted(data, key=lambda x: x[field], reverse=is_descending)


def order_by_many(
    data: List[Dict[str, Any]], fields: List[str]
) -> List[Dict[str, Any]]:
    """Orders the data by many fields

    Args:
        data: the list of records to sort
        fields: the fields to order by, if a field starts with "-" then order is descending

    Returns:
        the ordered list of records
    """

    def get_key(item) -> tuple:
        return tuple(
            (
                item.get(field)
                if not field.startswith("-")
                else _to_hash(item[field[1:]], negated=True)
            )
            for field in fields
        )

    return sorted(data, key=get_key)


def distinct_on(data: List[Dict[str, Any]], field: str) -> List[Dict[str, Any]]:
    """Returns the list of unique records basing on the field passed

    It picks the first record for a given unique value and ignores any duplicates.

    Args:
        data: the list of records that is to be filtered
        field: the field that distinguishes unique records from one another

    Returns:
        the list of unique records
    """
    items = {}

    for item in data:
        unique_value = item[field]

        # FIXME: Treat datetime special as mongodb reduces their precision
        if isinstance(unique_value, datetime):
            unique_value = unique_value.isoformat(timespec="milliseconds")

        if unique_value not in items:
            items[unique_value] = item

    return list(items.values())


def get_record(data: List[Dict[str, Any]], _filter: Dict[str, Any]) -> Dict[str, Any]:
    """Gets the first record in data which matches the given filter

    Args:
        data: list of records to get the record from
        _filter: partial dict that the given record should contain

    Returns:
        the first record that matches the given filter

    Raises:
        KeyError: {key}
    """
    try:
        return next(
            filter(lambda x: all([x[k] == v for k, v in _filter.items()]), data)
        )
    except StopIteration:
        raise KeyError(f"no match found for filter {_filter}")


def get_many_records(
    data: List[Dict[str, Any]], _filter: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Gets all records in data that match the given filter

    Args:
        data: list of records to get the record from
        _filter: partial dict that the given record should contain

    Returns:
        the records that match the given filter

    Raises:
        KeyError: {key}
    """
    try:
        return list(
            filter(lambda x: all([x[k] == v for k, v in _filter.items()]), data)
        )
    except IndexError:
        raise KeyError(f"no match found for filter {_filter}")


def get_range(
    data: List[Dict[str, Any]], field: str, from_: Any, to: Any
) -> List[Dict[str, Any]]:
    """Gets the list of records whose `field` value is between `from_` and `to` inclusive

    Args:
        data: list of records to get the records from
        field: the dict property to filter by
        from_: the lower inclusive boundary for the given field
        to: the upper inclusive boundary for the given field

    Returns:
        the list of records that have their values for the given field lying in the given range

    Raises:
        KeyError: {field}
    """
    return [v for v in data if from_ <= v[field] <= to]


def group_by(
    data: List[Dict[str, Any]], unique_keys: Tuple[str, ...]
) -> Dict[str, Any]:
    """Groups the props by the given unique keys

    Args:
        data: the list to group
        unique_keys: the keys to group by

    Returns:
        a nested dictionary each level representing a different unique_key
    """
    result = {}
    non_terminal_keys = unique_keys[:-1]
    terminal_key = unique_keys[-1]

    for prop in data:
        current_group = result

        for k in non_terminal_keys:
            unique_value = prop[k]
            group = current_group.setdefault(unique_value, {})
            current_group = group

        terminal_value = prop[terminal_key]
        try:
            current_group[terminal_value].append(prop)
        except KeyError:
            current_group[terminal_value] = [prop]

    return result


def copy_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Copies the list of dicts into a new immutable list of dicts

    Args:
        records: the list of records to copy immutably

    return
        New list of records with same values
    """
    return [{**item} for item in records]


def filter_by_equality(
    records: List[Dict[str, Any]], filters: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Filters the records that match the given filters

    It simply checks that the matched record has the properties in the filters dict

    Args:
        records: the data to filter
        filters: the properties that matched dicts should have

    Returns:
        the records that match the given filters
    """
    return [
        item for item in records if all([item.get(k) == v for k, v in filters.items()])
    ]


def with_incremental_timestamps(
    data: List[dict],
    fields: Sequence[str] = (
        "created_at",
        "updated_at",
    ),
) -> List[dict]:
    """Gets data that has timestamps, each record with an earlier timestamp than the next

    We update the fields passed with the corresponding timestamps

    Args:
        data: the list of dicts to attach timestamps to
        fields: the fields that should have the timestamps

    Returns:
        the data with timestamps
    """
    now = datetime.now(timezone.utc)
    return [
        {
            **item,
            **{
                field: get_timestamp_str(now + timedelta(minutes=idx))
                for field in fields
            },
        }
        for idx, item in enumerate(data)
    ]


def with_current_timestamps(
    data: List[dict],
    fields: Sequence[str] = ("updated_at",),
) -> List[dict]:
    """Gets data that has the current timestamp

    We update the fields passed with the corresponding timestamps

    Args:
        data: the list of dicts to attach timestamps to
        fields: the fields that should have the timestamps

    Returns:
        the data with timestamps
    """
    now = datetime.now(timezone.utc)
    return [
        {
            **item,
            **{field: get_timestamp_str(now) for field in fields},
        }
        for idx, item in enumerate(data)
    ]


def _to_hash(value: Any, negated: bool = False) -> tuple[int, ...] | int | float | None:
    """Converts a value to comparable hash that is negated if negated is True

    Args:
        value: the value whose comparable hash is to be obtained
        negated: whether to negate the hash to get a descending value or not

    Returns:
        the comparable hash
    """
    multiplier = 1 if not negated else -1
    if isinstance(value, str):
        return tuple(multiplier * ord(char) for char in value)
    if isinstance(value, (int, float)):
        return multiplier * value
    if value is None:
        return None
    raise TypeError(f"type {type(value)} cannot be hashed for ordering")


def paginate(
    data: List[T], skip: int = 0, limit: Optional[int] = None
) -> "PaginatedList[T]":
    """Paginates the data basing on the skip and the limit params

    Args:
        data: the data to paginate
        skip: the number of records to skip
        limit: the maximum number of records to return

    Returns:
        list of the data sliced according to the pagination info
    """
    slice_limit = limit
    if isinstance(slice_limit, int):
        slice_limit += skip
    return {"skip": skip, "limit": limit, "data": data[skip:slice_limit]}


class PaginatedList(TypedDict, Generic[T]):
    """The type for paginated responses"""

    skip: int
    limit: Optional[int]
    data: List[T]


class PaginationInfo(TypedDict):
    """The pagination info"""

    skip: int
    limit: Optional[float]
