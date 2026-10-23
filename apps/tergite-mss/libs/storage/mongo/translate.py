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
from ..base.query import LOGICAL_OPERATORS, Filter, is_operator_map, parse_sort
from ..base.schema import Schema, find_nested_model, resolve_field
from ..base.update import Update

KEY_FIELD = "_id"


def translate_filter(schema: Type[Schema], query_filter: Filter) -> Dict[str, Any]:
    """Translates the filter into a MongoDB query: the same document, with MongoDB's values"""
    query = {}
    for field, condition in query_filter.items():
        if field in LOGICAL_OPERATORS:
            query[field] = [translate_filter(schema, item) for item in condition]
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
    """Translates the update into a MongoDB update, dropping operators with no changes"""
    return {
        operator: {
            get_document_field(field): convert_to_bson_value(schema, field, value)
            for field, value in changes.items()
        }
        for operator, changes in update.items()
        if changes
    }


def translate_sort(sort: Sequence[str]) -> List[Tuple[str, int]]:
    return [
        (
            get_document_field(field),
            pymongo.DESCENDING if is_descending else pymongo.ASCENDING,
        )
        for field, is_descending in parse_sort(sort)
    ]


def get_document_field(field: str) -> str:
    """Names the field as MongoDB stores it: the `id` field is the document's `_id`"""
    return KEY_FIELD if field == "id" else field


def convert_to_bson_value(schema: Type[Schema], field: str, value: Any) -> Any:
    """Converts a value bound for the given field into what MongoDB stores"""
    if _is_id_path(schema, field):
        return _convert_to_object_ids(value)
    return _convert_to_bson(value)


def convert_to_document(schema: Type[Schema], record: Schema) -> Dict[str, Any]:
    """Converts the record into the document MongoDB stores; computed fields are not stored"""
    computed = set(type(record).model_computed_fields)
    data = record.model_dump(mode="python", exclude=computed or None)
    document = _convert_to_document_values(schema, data)
    if "id" in document:
        document[KEY_FIELD] = document.pop("id")
    return document


def convert_to_record(schema: Type[Schema], document: Mapping[str, Any]) -> Schema:
    """Converts a stored document into a record of the schema, validated"""
    data = {key: _convert_from_bson(value) for key, value in document.items()}
    key = data.pop(KEY_FIELD, None)
    if "id" in schema.model_fields:
        data["id"] = key
    return schema.model_validate(data)


@lru_cache(maxsize=None)
def _is_id_path(schema: Type[Schema], field: str) -> bool:
    return is_id_field(resolve_field(schema, field))


def _convert_to_document_values(
    model: Type[BaseModel], data: Mapping[str, Any]
) -> dict:
    document = {}
    for name, value in data.items():
        field_info = model.model_fields.get(name)
        nested = find_nested_model(field_info.annotation) if field_info else None
        if is_id_field(field_info):
            document[name] = _convert_to_object_ids(value)
        elif nested is not None and isinstance(value, dict):
            document[name] = _convert_to_document_values(nested, value)
        elif nested is not None and isinstance(value, list):
            document[name] = [
                _convert_to_document_values(nested, item)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            document[name] = _convert_to_bson(value)
    return document


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
