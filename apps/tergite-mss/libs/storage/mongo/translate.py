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

"""Translations between the storage layer's structs and MongoDB documents and operators

Ids are strings above the storage layer and ObjectIds in MongoDB, so every value bound for an
Id field becomes an ObjectId here, and every ObjectId read becomes a string.
"""
import enum
import re
import uuid
from collections import defaultdict
from functools import lru_cache
from pathlib import PurePath
from typing import Any, Dict, List, Mapping, Sequence, Tuple, Type

import pymongo
from bson import ObjectId
from pydantic import BaseModel

from ..base.ids import is_id_field
from ..base.query import And, Contains, Eq, Filter, In, Ne, NotIn, Or, Range, Sort
from ..base.schema import Schema, find_nested_model, resolve_field
from ..base.update import AddToSet, Inc, Pull, Set, SetOnInsert, Update

KEY_FIELD = "_id"
_MATCH_NOTHING = {KEY_FIELD: {"$in": []}}
_UPDATE_OPERATORS = {
    Set: "$set",
    SetOnInsert: "$setOnInsert",
    Inc: "$inc",
    AddToSet: "$addToSet",
    Pull: "$pull",
}


def translate_filter(schema: Type[Schema], where: Filter) -> Dict[str, Any]:
    """Translates the filter into a MongoDB query document"""
    if isinstance(where, (And, Or)):
        parts = [translate_filter(schema, item) for item in where.filters]
        if isinstance(where, Or):
            return {"$or": parts} if parts else _MATCH_NOTHING
        return {} if not parts else parts[0] if len(parts) == 1 else {"$and": parts}

    name = get_document_field(where.field)
    if isinstance(where, Eq):
        return {name: convert_to_bson_value(schema, where.field, where.value)}
    if isinstance(where, Ne):
        return {name: {"$ne": convert_to_bson_value(schema, where.field, where.value)}}
    if isinstance(where, In):
        return {
            name: {"$in": _convert_to_bson_values(schema, where.field, where.values)}
        }
    if isinstance(where, NotIn):
        return {
            name: {"$nin": _convert_to_bson_values(schema, where.field, where.values)}
        }
    if isinstance(where, Range):
        bounds = {"gt": where.gt, "gte": where.gte, "lt": where.lt, "lte": where.lte}
        return {
            name: {
                f"${op}": convert_to_bson_value(schema, where.field, value)
                for op, value in bounds.items()
                if value is not None
            }
        }
    if isinstance(where, Contains):
        options = {} if where.is_case_sensitive else {"$options": "i"}
        return {name: {"$regex": re.escape(where.text), **options}}
    raise TypeError(f"not a filter: {where!r}")


def translate_update(schema: Type[Schema], changes: Sequence[Update]) -> Dict[str, Any]:
    """Translates the changes into a MongoDB update document

    Raises:
        ValueError: there are no changes, which MongoDB refuses
    """
    if len(changes) == 0:
        raise ValueError("an update needs at least one change")

    update: Dict[str, Dict[str, Any]] = defaultdict(dict)
    for change in changes:
        operator = _UPDATE_OPERATORS[type(change)]
        value = change.amount if isinstance(change, Inc) else change.value
        update[operator][get_document_field(change.field)] = convert_to_bson_value(
            schema, change.field, value
        )
    return dict(update)


def translate_sort(sort: Sequence[Sort]) -> List[Tuple[str, int]]:
    return [
        (
            get_document_field(item.field),
            pymongo.DESCENDING if item.is_descending else pymongo.ASCENDING,
        )
        for item in sort
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
    """Converts the record into the document MongoDB stores"""
    document = _convert_to_document_values(schema, record.model_dump(mode="python"))
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


def _convert_to_bson_values(
    schema: Type[Schema], field: str, values: Sequence[Any]
) -> list:
    return [convert_to_bson_value(schema, field, value) for value in values]


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
