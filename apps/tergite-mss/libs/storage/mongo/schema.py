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

"""What each schema's storage facts become in MongoDB: a $jsonSchema validator and indexes"""
from typing import Any, Dict, List, Tuple, Type

import pymongo
from pymongo import IndexModel
from pymongo.collation import Collation

from ..base.schema import Schema, StorageSpec, is_list_field, resolve_field
from .translate import KEY_FIELD, get_document_field

CASE_INSENSITIVE = Collation("en", strength=2)
_ID_PATTERN = "^[0-9a-f]{24}$"
_MONGO_JSON_SCHEMA_KEYWORDS = {
    "additionalItems",
    "additionalProperties",
    "allOf",
    "anyOf",
    "bsonType",
    "dependencies",
    "description",
    "enum",
    "exclusiveMaximum",
    "exclusiveMinimum",
    "items",
    "maxItems",
    "maxLength",
    "maxProperties",
    "maximum",
    "minItems",
    "minLength",
    "minProperties",
    "minimum",
    "not",
    "oneOf",
    "pattern",
    "patternProperties",
    "properties",
    "required",
    "title",
    "uniqueItems",
}
_JSON_TO_BSON_TYPES = {
    "array": "array",
    "boolean": "bool",
    "integer": ["int", "long"],
    "null": "null",
    "number": "number",
    "object": "object",
    "string": "string",
}


def get_validator(schema: Type[Schema]) -> dict:
    """Gets the $jsonSchema validator that makes MongoDB reject records off the schema"""
    json_schema = schema.model_json_schema()
    mongo_schema = _convert_to_mongo_json_schema(
        json_schema, json_schema.get("$defs", {})
    )
    properties = mongo_schema.setdefault("properties", {})
    properties[KEY_FIELD] = properties.pop("id", {"bsonType": "objectId"})
    mongo_schema["required"] = [
        get_document_field(name) for name in mongo_schema.get("required", [])
    ]
    if not mongo_schema["required"]:
        del mongo_schema["required"]
    is_extra_allowed = schema.model_config.get("extra") == "allow"
    return {"$jsonSchema": {**mongo_schema, "additionalProperties": is_extra_allowed}}


def get_indexes(schema: Type[Schema]) -> List[IndexModel]:
    """Gets the indexes the schema's storage facts ask for, at most one per set of keys"""
    spec = schema.__storage__
    candidates: List[Tuple[List[Tuple[str, int]], Dict[str, Any]]] = []
    for group in spec.unique:
        keys = _get_index_keys(group)
        candidates.append((keys, {"unique": True, **_get_index_collation(spec, keys)}))
    for field in spec.case_insensitive:
        candidates.append((_get_index_keys(field), {"collation": CASE_INSENSITIVE}))
    if spec.expires is not None:
        candidates.append((_get_index_keys(spec.expires), {"expireAfterSeconds": 0}))
    list_references = [
        field
        for field in spec.references
        if is_list_field(resolve_field(schema, field))
    ]
    for field in (*list_references, *spec.indexed_lists):
        candidates.append((_get_index_keys(field), {}))
    for group in spec.indexes:
        candidates.append((_get_index_keys(group), {}))

    indexes: Dict[tuple, IndexModel] = {}
    for keys, options in candidates:
        if keys != [(KEY_FIELD, pymongo.ASCENDING)]:
            indexes.setdefault(tuple(keys), IndexModel(keys, **options))
    return list(indexes.values())


def _get_index_keys(group: str | Tuple[str, ...]) -> List[Tuple[str, int]]:
    fields = (group,) if isinstance(group, str) else group
    return [
        (
            get_document_field(field.lstrip("-")),
            pymongo.DESCENDING if field.startswith("-") else pymongo.ASCENDING,
        )
        for field in fields
    ]


def _get_index_collation(
    spec: StorageSpec, keys: List[Tuple[str, int]]
) -> Dict[str, Any]:
    is_case_insensitive = any(field in spec.case_insensitive for field, _ in keys)
    return {"collation": CASE_INSENSITIVE} if is_case_insensitive else {}


def _convert_to_mongo_json_schema(value: Any, definitions: Dict[str, Any]) -> Any:
    """Converts a pydantic JSON schema to MongoDB's dialect of JSON schema

    MongoDB supports neither references nor annotations like 'default' and 'format',
    and it validates BSON types, so dates and ObjectIds are not the strings JSON sees.
    """
    if isinstance(value, list):
        return [_convert_to_mongo_json_schema(item, definitions) for item in value]

    if not isinstance(value, dict):
        return value

    schema = dict(value)
    ref = schema.pop("$ref", None)
    if ref is not None:
        schema = {**definitions[ref.split("/")[-1]], **schema}

    if "const" in schema:
        schema["enum"] = [schema["const"]]

    if "prefixItems" in schema:
        schema["items"] = schema["prefixItems"]
        schema["additionalItems"] = False

    for bound in ("exclusiveMinimum", "exclusiveMaximum"):
        if not isinstance(schema.get(bound, True), bool):
            schema[bound.replace("exclusiveM", "m")] = schema[bound]
            schema[bound] = True

    json_type = schema.get("type")
    if json_type == "string" and schema.get("format") == "date-time":
        schema = {"bsonType": "date"}
    elif json_type == "string" and schema.get("pattern") == _ID_PATTERN:
        schema = {"bsonType": "objectId"}
    elif json_type is not None:
        schema["bsonType"] = _JSON_TO_BSON_TYPES[json_type]

    result = {}
    for key, item in schema.items():
        if key not in _MONGO_JSON_SCHEMA_KEYWORDS:
            continue

        if key in ("properties", "patternProperties"):
            result[key] = {
                k: _convert_to_mongo_json_schema(v, definitions)
                for k, v in item.items()
            }
        else:
            result[key] = _convert_to_mongo_json_schema(item, definitions)

    return result
