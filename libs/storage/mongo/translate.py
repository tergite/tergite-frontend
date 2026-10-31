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

"""Translations between the storage layer's dialect and MongoDB documents and operators

Ids are strings above the storage layer and ObjectIds in MongoDB, so every value bound for an
Id field becomes an ObjectId here, and every ObjectId read becomes a string.
"""
import enum
import uuid
from functools import lru_cache
from pathlib import PurePath
from typing import Any, Dict, List, Mapping, Sequence, Tuple, Type

import pymongo
from bson import ObjectId
from pydantic import BaseModel

from ..base.ids import is_id_field
from ..base.query import (
    ELEMENT_MATCH,
    LOGICAL_OPERATORS,
    Filter,
    is_operator_map,
    parse_sort,
)
from ..base.schema import Schema, find_nested_model, resolve_field
from ..base.update import Update

KEY_FIELD = "_id"


def translate_filter(schema: Type[Schema], query_filter: Filter) -> Dict[str, Any]:
    """Translates the filter into a MongoDB query: the same document, with MongoDB's values

    Args:
        schema: the schema of the records filtered
        query_filter: the filter, already checked against the schema

    Returns:
        the MongoDB query
    """
    query = {}
    for field, condition in query_filter.items():
        if field in LOGICAL_OPERATORS:
            query[field] = [translate_filter(schema, item) for item in condition]
        elif is_operator_map(condition) and ELEMENT_MATCH in condition:
            query[field] = {
                ELEMENT_MATCH: _translate_element_filter(
                    schema, field, condition[ELEMENT_MATCH]
                )
            }
        elif is_operator_map(condition):
            query[get_document_field(field)] = {
                operator: convert_to_bson_value(schema, field, operand)
                for operator, operand in condition.items()
            }
        else:
            query[get_document_field(field)] = convert_to_bson_value(
                schema, field, condition
            )
    return query


def translate_update(schema: Type[Schema], update: Update) -> Dict[str, Any]:
    """Translates the update into a MongoDB update, dropping operators with no changes

    Args:
        schema: the schema of the records updated
        update: the update, already checked against the schema

    Returns:
        the MongoDB update
    """
    return {
        operator: {
            get_document_field(field): convert_to_bson_value(schema, field, value)
            for field, value in changes.items()
        }
        for operator, changes in update.items()
        if changes
    }


def translate_sort(sort: Sequence[str]) -> List[Tuple[str, int]]:
    """Translates the sort into MongoDB's (field, direction) pairs

    Args:
        sort: the fields to sort by; a leading '-' sorts descending

    Returns:
        a (document field, pymongo direction) pair per field
    """
    return [
        (
            get_document_field(field),
            pymongo.DESCENDING if is_descending else pymongo.ASCENDING,
        )
        for field, is_descending in parse_sort(sort)
    ]


def get_document_field(field: str) -> str:
    """Names the field as MongoDB stores it: the `id` field is the document's `_id`

    Args:
        field: the schema's name for the field

    Returns:
        the document's name for the field
    """
    return KEY_FIELD if field == "id" else field


def convert_to_bson_value(schema: Type[Schema], field: str, value: Any) -> Any:
    """Converts a value bound for the given field into what MongoDB stores

    Args:
        schema: the schema of the record
        field: the field the value is bound for, dotted for a nested one
        value: the value, or a list of them for an operator such as `$in`

    Returns:
        the value as MongoDB stores it, e.g. an id as an ObjectId
    """
    if _is_id_path(schema, field):
        return _convert_to_object_ids(value)
    nested = _find_nested_model_at(schema, field)
    if nested is not None:
        return _convert_nested_value(nested, value)
    return _convert_to_bson(value)


def convert_to_document(schema: Type[Schema], record: Schema) -> Dict[str, Any]:
    """Converts the record into the document MongoDB stores; computed fields are not stored

    Args:
        schema: the schema of the record
        record: the record

    Returns:
        the document
    """
    computed = set(type(record).model_computed_fields)
    data = record.model_dump(mode="python", exclude=computed or None)
    document = _convert_to_document_values(schema, data)
    # MongoDB makes the _id of a record without an id, as SQL storage does
    record_id = document.pop("id", None)
    if record_id is not None:
        document[KEY_FIELD] = record_id
    return document


def convert_to_record(schema: Type[Schema], document: Mapping[str, Any]) -> Schema:
    """Converts a stored document into a record of the schema, validated

    Args:
        schema: the schema of the record
        document: the stored document

    Returns:
        the record

    Raises:
        ValidationError: the document does not fit the schema
    """
    data = {key: _convert_from_bson(value) for key, value in document.items()}
    key = data.pop(KEY_FIELD, None)
    if "id" in schema.model_fields:
        data["id"] = key
    return schema.model_validate(data)


@lru_cache(maxsize=None)
def _is_id_path(schema: Type[Schema], field: str) -> bool:
    return is_id_field(resolve_field(schema, field))


@lru_cache(maxsize=None)
def _find_nested_model_at(schema: Type[Schema], field: str) -> Any:
    field_info = resolve_field(schema, field)
    return find_nested_model(field_info.annotation) if field_info else None


def _translate_element_filter(
    schema: Type[Schema], field: str, element_filter: Filter
) -> Dict[str, Any]:
    """Translates a $elemMatch filter, whose fields are those of the list's elements"""
    prefixed_filter = {
        f"{field}.{element_field}": condition
        for element_field, condition in element_filter.items()
    }
    translated = translate_filter(schema, prefixed_filter)
    return {path[len(field) + 1 :]: value for path, value in translated.items()}


def _convert_to_document_values(
    model: Type[BaseModel], data: Mapping[str, Any]
) -> dict:
    document = {}
    for name, value in data.items():
        field_info = model.model_fields.get(name)
        nested = find_nested_model(field_info.annotation) if field_info else None
        if is_id_field(field_info):
            document[name] = _convert_to_object_ids(value)
        elif nested is not None:
            document[name] = _convert_nested_value(nested, value)
        else:
            document[name] = _convert_to_bson(value)
    return document


def _convert_nested_value(model: Type[BaseModel], value: Any) -> Any:
    """Converts a nested model's data, alone or in a list, into what MongoDB stores"""
    if isinstance(value, dict):
        return _convert_to_document_values(model, value)
    if isinstance(value, list):
        return [_convert_nested_value(model, item) for item in value]
    return _convert_to_bson(value)


def _convert_to_object_ids(value: Any) -> Any:
    if isinstance(value, str):
        return ObjectId(value)
    if isinstance(value, (list, tuple, set)):
        return [_convert_to_object_ids(item) for item in value]
    return value


def _convert_to_bson(value: Any) -> Any:
    """Converts the Python values pymongo cannot encode into ones it can"""
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (uuid.UUID, PurePath)):
        return str(value)
    if isinstance(value, (set, frozenset, tuple, list)):
        return [_convert_to_bson(item) for item in value]
    if isinstance(value, dict):
        return {key: _convert_to_bson(item) for key, item in value.items()}
    return value


def _convert_from_bson(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [_convert_from_bson(item) for item in value]
    if isinstance(value, dict):
        return {key: _convert_from_bson(item) for key, item in value.items()}
    return value
