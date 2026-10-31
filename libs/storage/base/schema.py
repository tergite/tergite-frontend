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
import logging
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    ClassVar,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
    get_args,
    get_origin,
)

from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

from .exc import UnknownFieldError

_logger = logging.getLogger(__name__)


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
        should_skip_invalid: whether reads leave out stored records that fail validation,
            rather than raise; counts still include them, so a page may come up short
    """

    table: str
    key: str = "id"
    unique: Tuple[str | Tuple[str, ...], ...] = ()
    case_insensitive: Tuple[str, ...] = ()
    expires: Optional[str] = None
    references: Mapping[str, Type["Schema"]] = field(default_factory=dict)
    indexed_lists: Tuple[str, ...] = ()
    indexes: Tuple[str | Tuple[str, ...], ...] = ()
    should_skip_invalid: bool = False


class Schema(BaseModel):
    """The base of every stored schema, which sets its `__storage__`"""

    __storage__: ClassVar[StorageSpec]


T = TypeVar("T", bound=Schema)


def read_stored(schema: Type[T], data: Any, convert: Callable[[Any], T]) -> Optional[T]:
    """Converts stored data into a record, or None if it fails validation and the schema
    skips invalid records

    Args:
        schema: the schema of the record
        data: the data as stored
        convert: turns the stored data into a record, validating it

    Returns:
        the record, or None if it is invalid and the schema skips invalid records

    Raises:
        ValidationError: the data fails validation and the schema does not skip it
    """
    try:
        return convert(data)
    except ValidationError as exp:
        if not schema.__storage__.should_skip_invalid:
            raise
        # the stored values stay out of the log, as they may hold secrets
        fields = ", ".join(".".join(map(str, error["loc"])) for error in exp.errors())
        _logger.warning(f"left out a stored {schema.__name__} invalid in: {fields}")
        return None


def resolve_field(schema: Type[BaseModel], path: str) -> Optional[FieldInfo]:
    """Gets the field a dotted path names, or None for a path into a free-form mapping

    A model that allows extra fields is free-form beyond the fields it declares.

    Args:
        schema: the model the path starts from
        path: the field's dotted path, e.g. `timestamps.started`

    Returns:
        the field, or None for a path into a free-form mapping

    Raises:
        UnknownFieldError: the schema has no such field
    """
    field_info: Optional[FieldInfo] = None
    annotation: Any = schema
    for part in path.split("."):
        model = find_nested_model(annotation)
        if model is None and _is_open_mapping(annotation):
            return None
        if model is not None and part not in model.model_fields:
            if model.model_config.get("extra") == "allow":
                return None
        if model is None or part not in model.model_fields:
            raise UnknownFieldError(f"{schema.__name__} has no field '{path}'")
        field_info = model.model_fields[part]
        annotation = field_info.annotation
    return field_info


def is_list_field(field_info: Optional[FieldInfo]) -> bool:
    """Whether the field holds a list, possibly Optional

    Args:
        field_info: the field, or None for a free-form one

    Returns:
        True if the field holds a list, tuple or set
    """
    if field_info is None:
        return False
    return any(
        get_origin(arg) in (list, tuple, set)
        for arg in (field_info.annotation, *get_args(field_info.annotation))
    )


def is_model_list(field_info: Optional[FieldInfo]) -> bool:
    """Whether the field holds a list of models

    Args:
        field_info: the field, or None for a free-form one

    Returns:
        True if the field holds a list of models
    """
    return (
        is_list_field(field_info)
        and find_nested_model(field_info.annotation) is not None
    )


def find_nested_model(annotation: Any) -> Optional[Type[BaseModel]]:
    """Gets the model the annotation holds, alone or in an Optional, List or Union

    Args:
        annotation: the type annotation

    Returns:
        the first model found, or None if it holds none
    """
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for arg in get_args(annotation):
        model = find_nested_model(arg)
        if model is not None:
            return model
    return None


def _is_open_mapping(annotation: Any) -> bool:
    return annotation in (dict, Any) or get_origin(annotation) in (dict, Mapping)
