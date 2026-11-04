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
"""The SQL tables of the schemas, derived from their fields and `__storage__`

A schema's table has a column per scalar field and a JSON column per nested one, which is
always read and written whole. A field in `indexed_lists`, or a list field in `references`,
has a child table instead: one row per element, with its position, so that its elements can
be queried and written one at a time. An element that is a model gets a column per field.
Each table also has a `row_id` that orders rows as they were inserted, as MongoDB orders
documents.
"""

import enum
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePath
from types import NoneType, UnionType
from typing import (
    Annotated,
    Any,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import to_jsonable_python
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    TypeDecorator,
    UniqueConstraint,
    func,
)

from ..base.exc import StorageSpecError
from ..base.ids import is_id_field
from ..base.schema import Schema, find_nested_model, is_list_field

ROW_ID = "row_id"
POSITION = "position"
# SQLite numbers rows only in an INTEGER primary key
_ROW_ID_TYPE = BigInteger().with_variant(Integer(), "sqlite")


class UtcDateTime(TypeDecorator):
    """A timezone-aware datetime, kept in UTC, that reads back aware on every database"""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        """Gives a naive datetime UTC's timezone before it is written

        Args:
            value: the value written
            dialect: the database's dialect

        Returns:
            the value, aware if a datetime
        """
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        """Gives a naive datetime UTC's timezone as it is read

        Args:
            value: the value read
            dialect: the database's dialect

        Returns:
            the value, aware if a datetime
        """
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


@dataclass(frozen=True)
class ListTable:
    """The child table of a list field: one row per element, at its position

    Attributes:
        table: the child table
        parent_column: the column holding the key of the element's record
        value_column: the column holding a scalar element; None for a model's
        element_model: the model of each element, whose fields are columns; None for scalars
    """

    table: Table
    parent_column: str
    value_column: Optional[str]
    element_model: Optional[Type[BaseModel]]


@dataclass(frozen=True)
class SchemaTables:
    """A schema's table, and the child tables of its list fields"""

    schema: Type[Schema]
    table: Table
    list_tables: Dict[str, ListTable]
    json_fields: Tuple[str, ...]
    # fields that cannot hold None, whose NULL means MongoDB's missing field: the default
    non_null_fields: Tuple[str, ...]


def get_schema_tables(
    metadata: MetaData, schemas: Sequence[Type[Schema]]
) -> Dict[Type[Schema], SchemaTables]:
    """Gets the tables of each schema, adding them to the metadata

    Schemas are added referenced-first, so that a foreign key finds its table.

    Args:
        metadata: the metadata to add the tables to
        schemas: the schemas

    Returns:
        the tables of each schema

    Raises:
        StorageSpecError: a list field that is unique, or a key that is a list
    """
    schema_tables: Dict[Type[Schema], SchemaTables] = {}
    for schema in _order_by_references(schemas):
        schema_tables[schema] = _get_tables_of(metadata, schema, schema_tables)
    return schema_tables


def get_metadata(schemas: Sequence[Type[Schema]]) -> MetaData:
    """Gets the metadata of every table of the schemas, as migrations compare it

    Args:
        schemas: the schemas

    Returns:
        the metadata
    """
    metadata = MetaData()
    get_schema_tables(metadata, schemas)
    return metadata


def get_child_fields(schema: Type[Schema]) -> Tuple[str, ...]:
    """Gets the list fields kept in child tables

    Args:
        schema: the schema

    Returns:
        the fields in `indexed_lists`, then the list fields in `references`
    """
    spec = schema.__storage__
    referenced_lists = tuple(
        field for field in spec.references if is_list_field(schema.model_fields[field])
    )
    return (*spec.indexed_lists, *referenced_lists)


def get_singular(table_name: str) -> str:
    """Gets the singular of a table's name, for naming its child tables

    Args:
        table_name: the table's name, e.g. auth_projects

    Returns:
        the name without a trailing 's', e.g. auth_project
    """
    return table_name[:-1] if table_name.endswith("s") else table_name


def get_child_rows(
    list_table: ListTable, key: Any, elements: Sequence[Any]
) -> List[Dict[str, Any]]:
    """Gets the child-table rows of a record's list elements, in their order

    Args:
        list_table: the child table of the list field
        key: the key of the record
        elements: the list's elements

    Returns:
        a row per element
    """
    if list_table.element_model is None:
        return [
            {
                list_table.parent_column: key,
                list_table.value_column: element,
                POSITION: position,
            }
            for position, element in enumerate(elements)
        ]

    rows = []
    for position, element in enumerate(elements):
        if isinstance(element, BaseModel):
            element = element.model_dump()
        row = {list_table.parent_column: key, POSITION: position}
        for name in list_table.element_model.model_fields:
            value = element.get(name)
            if isinstance(list_table.table.c[name].type, JSON):
                row[name] = to_jsonable_python(value)
            else:
                row[name] = convert_to_column_value(value)
        rows.append(row)
    return rows


def convert_to_column_value(value: Any) -> Any:
    """Converts a value into what a SQL column holds: an enum's value, a UUID's text

    Args:
        value: the value

    Returns:
        the value as the column holds it
    """
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (uuid.UUID, PurePath)):
        return str(value)
    return value


def get_element(list_table: ListTable, row: Mapping[str, Any]) -> Any:
    """Gets the list element a child-table row holds

    Args:
        list_table: the child table of the list field
        row: the child-table row

    Returns:
        the scalar element, or a dict of a model element's fields
    """
    if list_table.element_model is None:
        return row[list_table.value_column]
    return {name: row[name] for name in list_table.element_model.model_fields}


def _get_tables_of(
    metadata: MetaData,
    schema: Type[Schema],
    schema_tables: Dict[Type[Schema], SchemaTables],
) -> SchemaTables:
    spec = schema.__storage__
    child_fields = get_child_fields(schema)
    columns: List[Any] = [
        Column(ROW_ID, _ROW_ID_TYPE, primary_key=True, autoincrement=True)
    ]
    json_fields = []
    for name, field_info in schema.model_fields.items():
        if name in child_fields:
            continue
        column_type = _get_column_type(field_info)
        if isinstance(column_type, JSON):
            json_fields.append(name)
        referenced = spec.references.get(name)
        foreign_keys = []
        if referenced is not None:
            target = schema_tables[referenced]
            foreign_keys.append(
                ForeignKey(
                    target.table.c[referenced.__storage__.key], ondelete="SET NULL"
                )
            )
        is_key = name == spec.key
        columns.append(
            Column(
                name,
                column_type,
                *foreign_keys,
                nullable=not is_key,
                unique=is_key,
            )
        )

    table = Table(spec.table, metadata, *columns)
    for group in spec.unique:
        fields = (group,) if isinstance(group, str) else tuple(group)
        if any(field in child_fields for field in fields):
            raise StorageSpecError(f"{schema.__name__}: a list field cannot be unique")
        if fields == (spec.key,):
            continue
        if len(fields) == 1 and fields[0] in spec.case_insensitive:
            Index(
                f"ux_{spec.table}_{fields[0]}",
                func.lower(table.c[fields[0]]),
                unique=True,
            )
        else:
            table.append_constraint(
                UniqueConstraint(*fields, name=f"ux_{spec.table}_{'_'.join(fields)}")
            )
    for group in spec.indexes:
        fields = (group,) if isinstance(group, str) else tuple(group)
        names = [field.lstrip("-") for field in fields]
        if names == [spec.key] or any("." in name for name in names):
            continue
        index_columns = [
            table.c[name].desc() if field.startswith("-") else table.c[name]
            for field, name in zip(fields, names)
        ]
        Index(f"ix_{spec.table}_{'_'.join(names)}", *index_columns)
    if spec.expires is not None:
        Index(f"ix_{spec.table}_{spec.expires}", table.c[spec.expires])

    list_tables = {
        field: _get_list_table(metadata, schema, table, field, schema_tables)
        for field in child_fields
    }
    for group in spec.indexes:
        fields = (group,) if isinstance(group, str) else tuple(group)
        if any("." in field for field in fields):
            _add_element_index(list_tables, fields)
    non_null_fields = tuple(
        name
        for name, field_info in schema.model_fields.items()
        if not _is_none_allowed(field_info.annotation)
    )
    return SchemaTables(
        schema=schema,
        table=table,
        list_tables=list_tables,
        json_fields=tuple(json_fields),
        non_null_fields=non_null_fields,
    )


def _get_list_table(
    metadata: MetaData,
    schema: Type[Schema],
    table: Table,
    field: str,
    schema_tables: Dict[Type[Schema], SchemaTables],
) -> ListTable:
    """Gets the child table of a list field, e.g. auth_project_user_ids for user_ids"""
    spec = schema.__storage__
    singular = get_singular(spec.table)
    parent_column = f"{singular}_id" if spec.key == "id" else spec.key
    element_field = _get_element_field(schema, field)
    element_model = find_nested_model(element_field.annotation)
    if element_model is not None:
        child = Table(
            f"{singular}_{field}",
            metadata,
            Column(
                parent_column,
                table.c[spec.key].type,
                ForeignKey(table.c[spec.key], ondelete="CASCADE"),
                primary_key=True,
            ),
            Column(POSITION, Integer, primary_key=True),
            *(
                Column(name, _get_column_type(field_info))
                for name, field_info in element_model.model_fields.items()
            ),
        )
        return ListTable(
            table=child,
            parent_column=parent_column,
            value_column=None,
            element_model=element_model,
        )

    value_column = field[:-1] if field.endswith("s") else field
    element_type = _get_column_type(element_field)
    value_foreign_keys = []
    referenced = spec.references.get(field)
    if referenced is not None:
        target = schema_tables[referenced]
        value_foreign_keys.append(
            ForeignKey(target.table.c[referenced.__storage__.key], ondelete="CASCADE")
        )

    child = Table(
        f"{singular}_{field}",
        metadata,
        Column(
            parent_column,
            table.c[spec.key].type,
            ForeignKey(table.c[spec.key], ondelete="CASCADE"),
            primary_key=True,
        ),
        Column(value_column, element_type, *value_foreign_keys, primary_key=True),
        Column(POSITION, Integer, nullable=False),
    )
    Index(f"ix_{singular}_{field}_{value_column}", child.c[value_column])
    return ListTable(
        table=child,
        parent_column=parent_column,
        value_column=value_column,
        element_model=None,
    )


def _get_column_type(field_info: FieldInfo) -> Any:
    """Gets the SQL type of a field: a scalar's own, or JSON for anything nested"""
    if is_id_field(field_info) and not is_list_field(field_info):
        return String(24)
    annotation = _unwrap_optional(field_info.annotation)
    if get_origin(annotation) is Literal:
        return String()
    if not isinstance(annotation, type):
        return JSON(none_as_null=True)
    if issubclass(annotation, bool):
        return Boolean()
    if issubclass(annotation, enum.Enum):
        values = [member.value for member in annotation]
        if all(isinstance(value, int) for value in values):
            return BigInteger()
        return String()
    if issubclass(annotation, int):
        return BigInteger()
    if issubclass(annotation, float):
        return Float()
    if issubclass(annotation, datetime):
        return UtcDateTime()
    if issubclass(annotation, (str, uuid.UUID, PurePath)):
        return String()
    return JSON(none_as_null=True)


def _get_element_field(schema: Type[Schema], field: str) -> FieldInfo:
    """Gets the field of a list field's elements, with their annotation's metadata"""
    annotation = _unwrap_optional(schema.model_fields[field].annotation)
    (element_annotation,) = get_args(annotation) or (Any,)
    return FieldInfo.from_annotation(element_annotation)


def _is_none_allowed(annotation: Any) -> bool:
    if annotation in (Any, None, NoneType):
        return True
    return get_origin(annotation) in (Union, UnionType) and NoneType in get_args(
        annotation
    )


def _unwrap_optional(annotation: Any) -> Any:
    """Gets the type an annotation names: through `type` aliases, Annotated and Optional"""
    if isinstance(annotation, TypeAliasType):
        return _unwrap_optional(annotation.__value__)
    if get_origin(annotation) is Annotated:
        return _unwrap_optional(get_args(annotation)[0])
    if get_origin(annotation) in (Union, UnionType):
        args = [arg for arg in get_args(annotation) if arg is not NoneType]
        if len(args) == 1:
            return _unwrap_optional(args[0])
    return annotation


def _order_by_references(schemas: Sequence[Type[Schema]]) -> List[Type[Schema]]:
    """Orders the schemas so that each comes after those it references"""
    ordered: List[Type[Schema]] = []
    for schema in schemas:
        _add_after_references(schema, ordered, set(schemas))
    return ordered


def _add_after_references(
    schema: Type[Schema], ordered: List[Type[Schema]], schemas: set
) -> None:
    if schema in ordered:
        return
    for referenced in schema.__storage__.references.values():
        if referenced is not schema and referenced in schemas:
            _add_after_references(referenced, ordered, schemas)
    ordered.append(schema)


def _add_element_index(
    list_tables: Dict[str, ListTable], fields: Tuple[str, ...]
) -> None:
    """Indexes fields of a list's model elements, e.g. ("accounts.name", "accounts.id")

    Raises:
        StorageSpecError: the fields are not all in one list of models
    """
    list_fields = {field.lstrip("-").split(".")[0] for field in fields}
    list_table = list_tables.get(next(iter(list_fields)))
    if len(list_fields) > 1 or list_table is None or list_table.element_model is None:
        raise StorageSpecError(f"{fields} are not all fields of one list of models")
    child = list_table.table
    names = [field.lstrip("-").split(".", 1)[1] for field in fields]
    Index(f"ix_{child.name}_{'_'.join(names)}", *(child.c[name] for name in names))
