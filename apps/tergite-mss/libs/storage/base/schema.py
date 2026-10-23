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

"""The base of stored schemas and the storage facts each declares"""
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping, Optional, Tuple, Type, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .exc import UnknownFieldError


@dataclass(frozen=True)
class StorageSpec:
    """How a schema is stored, in terms that name no database technology

    Attributes:
        table: the table, or collection, that holds the records
        key: the field every record is fetched by
        unique: fields, or tuples of fields together, that no two records share
        case_insensitive: string fields compared without case, in queries and uniqueness
        expires: a datetime field after which the record is deleted
        references: fields holding keys of another schema; a list field holds many
        indexed_lists: other list fields whose elements are queried one at a time
        indexes: fields, or tuples of fields together, that queries filter or sort on;
            a leading '-' marks a descending field
    """

    table: str
    key: str = "id"
    unique: Tuple[str | Tuple[str, ...], ...] = ()
    case_insensitive: Tuple[str, ...] = ()
    expires: Optional[str] = None
    references: Mapping[str, Type["Schema"]] = field(default_factory=dict)
    indexed_lists: Tuple[str, ...] = ()
    indexes: Tuple[str | Tuple[str, ...], ...] = ()


class Schema(BaseModel):
    """The base of every stored schema, which sets its `__storage__`"""

    __storage__: ClassVar[StorageSpec]


def resolve_field(schema: Type[BaseModel], path: str) -> Optional[FieldInfo]:
    """Gets the field a dotted path names, or None for a path into a free-form mapping

    Raises:
        UnknownFieldError: the schema has no such field
    """
    field_info: Optional[FieldInfo] = None
    annotation: Any = schema
    for part in path.split("."):
        model = _find_model(annotation)
        if model is None and _is_open_mapping(annotation):
            return None
        if model is None or part not in model.model_fields:
            raise UnknownFieldError(f"{schema.__name__} has no field '{path}'")
        field_info = model.model_fields[part]
        annotation = field_info.annotation
    return field_info


def is_list_field(field_info: Optional[FieldInfo]) -> bool:
    """Whether the field holds a list, possibly Optional"""
    if field_info is None:
        return False
    return any(
        get_origin(arg) in (list, tuple, set)
        for arg in (field_info.annotation, *get_args(field_info.annotation))
    )


def _find_model(annotation: Any) -> Optional[Type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for arg in get_args(annotation):
        model = _find_model(arg)
        if model is not None:
            return model
    return None


def _is_open_mapping(annotation: Any) -> bool:
    return annotation in (dict, Any) or get_origin(annotation) in (dict, Mapping)
