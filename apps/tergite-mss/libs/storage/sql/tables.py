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
be queried and written one at a time. Each table also has a `row_id` that orders rows as
they were inserted, as MongoDB orders documents.
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
    Sequence,
    Tuple,
    Type,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
)

from pydantic.fields import FieldInfo
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
from ..base.schema import Schema, is_list_field

ROW_ID = "row_id"
POSITION = "position"
# SQLite numbers rows only in an INTEGER primary key
_ROW_ID_TYPE = BigInteger().with_variant(Integer(), "sqlite")


class UtcDateTime(TypeDecorator):
    """A timezone-aware datetime, kept in UTC, that reads back aware on every database"""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


@dataclass(frozen=True)
class ListTable:
    """The child table of a list field: one row per element, at its position"""

    table: Table
    parent_column: str
    value_column: str


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

    Raises:
        StorageSpecError: a list field that is unique, or a key that is a list
    """
    schema_tables: Dict[Type[Schema], SchemaTables] = {}
    for schema in _order_by_references(schemas):
        schema_tables[schema] = _get_tables_of(metadata, schema, schema_tables)
    return schema_tables


def get_metadata(schemas: Sequence[Type[Schema]]) -> MetaData:
    """Gets the metadata of every table of the schemas, as migrations compare it"""
    metadata = MetaData()
    get_schema_tables(metadata, schemas)
    return metadata


def get_child_fields(schema: Type[Schema]) -> Tuple[str, ...]:
    """The list fields kept in child tables"""
    spec = schema.__storage__
    referenced_lists = tuple(
        field for field in spec.references if is_list_field(schema.model_fields[field])
    )
    return (*spec.indexed_lists, *referenced_lists)


def get_singular(table_name: str) -> str:
    return table_name[:-1] if table_name.endswith("s") else table_name


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
        if names == [spec.key]:
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
    value_column = field[:-1] if field.endswith("s") else field
    element_type = _get_column_type(_get_element_field(schema, field))
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
        table=child, parent_column=parent_column, value_column=value_column
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
