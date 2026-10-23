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
"""Translations of the storage layer's dialect into SQLAlchemy Core

Every value becomes a bound parameter and every field is resolved against the schema's
columns, so no caller's input reaches SQL text. A list field kept in a child table is
matched with an EXISTS on that table. JSON columns are read and written whole, so a filter,
sort or update that reaches into one is refused.
"""
import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any, Dict, List, Sequence, Tuple

from pydantic_core import to_jsonable_python
from sqlalchemy import ColumnElement, and_, exists, false, func, not_, or_, select, true

from ..base.exc import QueryError
from ..base.query import Filter, is_operator_map, parse_sort
from ..base.update import Update
from .tables import ROW_ID, ListTable, SchemaTables


@dataclass
class Changes:
    """An update as SQL runs it: column values, then the child-table writes"""

    values: Dict[str, Any] = field(default_factory=dict)
    values_on_insert: Dict[str, Any] = field(default_factory=dict)
    list_replacements: Dict[str, List[Any]] = field(default_factory=dict)
    list_additions: List[Tuple[str, Any]] = field(default_factory=list)
    list_removals: List[Tuple[str, Any]] = field(default_factory=list)


def translate_filter(tables: SchemaTables, query_filter: Filter) -> ColumnElement:
    """Translates the filter into a WHERE clause on the schema's table, unexpired rows only"""
    conditions = [_translate_conditions(tables, query_filter)]
    expires_field = tables.schema.__storage__.expires
    if expires_field is not None:
        column = tables.table.c[expires_field]
        conditions.append(or_(column.is_(None), column > datetime.now(timezone.utc)))
    return and_(*conditions)


def translate_sort(tables: SchemaTables, sort: Sequence[str]) -> List[ColumnElement]:
    """Translates the sort, None first as MongoDB sorts it, ties in insertion order"""
    order = []
    for field_name, is_descending in parse_sort(sort):
        column = _get_column(tables, field_name)
        if is_descending:
            order.append(column.desc().nulls_last())
        else:
            order.append(column.asc().nulls_first())
    order.append(tables.table.c[ROW_ID].asc())
    return order


def translate_update(tables: SchemaTables, update: Update) -> Changes:
    """Translates the update into column values and child-table writes

    Raises:
        QueryError: the update changes the key, or reaches into a JSON field
    """
    changes = Changes()
    key = tables.schema.__storage__.key
    for operator, fields in update.items():
        for field_name, value in fields.items():
            if field_name == key and operator != "$setOnInsert":
                raise QueryError(
                    f"an update cannot change {tables.schema.__name__}.{key}"
                )
            if operator == "$set" and field_name in tables.list_tables:
                changes.list_replacements[field_name] = [
                    convert_to_column_value(item) for item in value
                ]
            elif operator == "$set":
                changes.values[field_name] = _convert_to_written_value(
                    tables, field_name, value
                )
            elif operator == "$setOnInsert":
                changes.values_on_insert[field_name] = _convert_to_written_value(
                    tables, field_name, value
                )
            elif operator == "$inc":
                column = _get_column(tables, field_name)
                changes.values[field_name] = func.coalesce(column, 0) + value
            elif operator == "$addToSet":
                _get_list_table(tables, field_name)
                changes.list_additions.append(
                    (field_name, convert_to_column_value(value))
                )
            elif operator == "$pull":
                _get_list_table(tables, field_name)
                changes.list_removals.append(
                    (field_name, convert_to_column_value(value))
                )
    return changes


def convert_to_column_value(value: Any) -> Any:
    """Converts a value into what a SQL column holds: an enum's value, a UUID's text"""
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (uuid.UUID, PurePath)):
        return str(value)
    return value


def _convert_to_written_value(tables: SchemaTables, field_name: str, value: Any) -> Any:
    """Converts a value set whole into its column's: JSON for a JSON field

    Raises:
        QueryError: the field is part of a JSON field, which is written whole
    """
    if field_name in tables.json_fields:
        return to_jsonable_python(value)
    _get_column(tables, field_name)
    return convert_to_column_value(value)


def _translate_conditions(tables: SchemaTables, query_filter: Filter) -> ColumnElement:
    conditions = []
    for field_name, condition in query_filter.items():
        if field_name == "$and":
            conditions.append(
                and_(*(_translate_conditions(tables, item) for item in condition))
            )
        elif field_name == "$or":
            conditions.append(
                or_(*(_translate_conditions(tables, item) for item in condition))
            )
        elif field_name in tables.list_tables:
            conditions.append(_translate_list_condition(tables, field_name, condition))
        else:
            conditions.append(
                _translate_column_condition(tables, field_name, condition)
            )
    return and_(true(), *conditions)


def _translate_column_condition(
    tables: SchemaTables, field_name: str, condition: Any
) -> ColumnElement:
    column = _get_column(tables, field_name)
    is_case_insensitive = field_name in tables.schema.__storage__.case_insensitive
    if is_case_insensitive:
        column = func.lower(column)
    operators = condition if is_operator_map(condition) else {"$eq": condition}

    clauses = []
    for operator, operand in operators.items():
        if operator == "$in":
            values = [_convert_operand(item, is_case_insensitive) for item in operand]
            clauses.append(_get_any_of_clause(column, values))
        elif operator == "$nin":
            values = [_convert_operand(item, is_case_insensitive) for item in operand]
            clauses.append(_get_none_of_clause(column, values))
        elif operator == "$eq":
            clauses.append(
                _get_equality_clause(
                    column, _convert_operand(operand, is_case_insensitive)
                )
            )
        elif operator == "$ne":
            value = _convert_operand(operand, is_case_insensitive)
            clauses.append(_get_inequality_clause(column, value))
        elif operator == "$gt":
            clauses.append(column > _convert_operand(operand, is_case_insensitive))
        elif operator == "$gte":
            clauses.append(column >= _convert_operand(operand, is_case_insensitive))
        elif operator == "$lt":
            clauses.append(column < _convert_operand(operand, is_case_insensitive))
        elif operator == "$lte":
            clauses.append(column <= _convert_operand(operand, is_case_insensitive))
    return and_(*clauses)


def _convert_operand(operand: Any, is_case_insensitive: bool) -> Any:
    value = convert_to_column_value(operand)
    if is_case_insensitive and isinstance(value, str):
        return value.lower()
    return value


def _translate_list_condition(
    tables: SchemaTables, field_name: str, condition: Any
) -> ColumnElement:
    """Matches a list field as MongoDB does: a value or $in matches a list holding it"""
    list_table = tables.list_tables[field_name]
    operators = condition if is_operator_map(condition) else {"$eq": condition}

    clauses = []
    for operator, operand in operators.items():
        if operator in ("$eq", "$ne") and isinstance(operand, list):
            raise QueryError(
                f"list field '{field_name}' is matched by element, not whole"
            )
        if operator == "$eq":
            clauses.append(_get_list_membership_clause(tables, list_table, [operand]))
        elif operator == "$ne":
            clauses.append(
                not_(_get_list_membership_clause(tables, list_table, [operand]))
            )
        elif operator == "$in":
            clauses.append(_get_list_membership_clause(tables, list_table, operand))
        elif operator == "$nin":
            clauses.append(
                not_(_get_list_membership_clause(tables, list_table, operand))
            )
        else:
            raise QueryError(f"list field '{field_name}' takes no {operator}")
    return and_(*clauses)


def _get_list_membership_clause(
    tables: SchemaTables, list_table: ListTable, values: Sequence[Any]
) -> ColumnElement:
    child = list_table.table
    key = tables.schema.__storage__.key
    values = [convert_to_column_value(value) for value in values if value is not None]
    if not values:
        return false()
    return exists(
        select(1).where(
            child.c[list_table.parent_column] == tables.table.c[key],
            child.c[list_table.value_column].in_(values),
        )
    )


def _get_equality_clause(column: ColumnElement, value: Any) -> ColumnElement:
    """MongoDB equality: None matches a null or missing field"""
    if value is None:
        return column.is_(None)
    return column == value


def _get_inequality_clause(column: ColumnElement, value: Any) -> ColumnElement:
    """MongoDB inequality: a null or missing field differs from any value but None"""
    if value is None:
        return column.is_not(None)
    return or_(column != value, column.is_(None))


def _get_any_of_clause(column: ColumnElement, values: List[Any]) -> ColumnElement:
    known_values = [value for value in values if value is not None]
    clause = column.in_(known_values) if known_values else false()
    if len(known_values) < len(values):
        return or_(clause, column.is_(None))
    return clause


def _get_none_of_clause(column: ColumnElement, values: List[Any]) -> ColumnElement:
    """MongoDB $nin: a null or missing field is none of the values, unless one is None"""
    known_values = [value for value in values if value is not None]
    clause = column.not_in(known_values) if known_values else true()
    if len(known_values) < len(values):
        return and_(clause, column.is_not(None))
    return or_(clause, column.is_(None))


def _get_column(tables: SchemaTables, field_name: str) -> ColumnElement:
    """Gets the column of a field

    Raises:
        QueryError: the field is in a JSON column, a list kept in a child table, or
            undeclared
    """
    if field_name in tables.list_tables:
        raise QueryError(f"list field '{field_name}' is matched by element")
    if "." in field_name or field_name in tables.json_fields:
        raise QueryError(f"'{field_name}' is in a JSON column, which is read whole")
    if field_name not in tables.table.c:
        # a schema that allows extra fields declares no column for them
        raise QueryError(f"'{field_name}' is not a column of {tables.table.name}")
    return tables.table.c[field_name]


def _get_list_table(tables: SchemaTables, field_name: str) -> ListTable:
    if field_name not in tables.list_tables:
        raise QueryError(f"'{field_name}' is not a list kept in its own table")
    return tables.list_tables[field_name]
