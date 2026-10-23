# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import asyncio
from contextlib import suppress
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Type

import pymongo
from beanie import Document, SortDirection, init_beanie
from loguru import logger
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pydantic import ValidationError
from pymongo import ReturnDocument
from pymongo.errors import CollectionInvalid

from .date_time import get_current_timestamp
from .exc import DatabaseError, NotFoundError
from .models import ModelOrDict, parse_record

_CONNECTIONS = {}
# the keywords that mongodb's draft-4 dialect of JSON schema understands
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
# the pattern beanie gives PydanticObjectId in its JSON schema
_OBJECT_ID_PATTERN = "^[0-9a-f]{24}$"


async def init_strict_beanie(
    database: AsyncIOMotorDatabase | None = None,
    connection_string: str | None = None,
    document_models: Sequence[type[Document]] = (),
    allow_index_dropping: bool = False,
    recreate_views: bool = False,
    multiprocessing_mode: bool = False,
    skip_indexes: bool = False,
):
    """Initializes beanie with strict mongodb schemas.

    This ensures the best of both worlds i.e. flexibility in development
    and predictability in operation

    Args:
        database: motor database instance
        connection_string: MongoDB connection string
        document_models: model classes
        allow_index_dropping: if index dropping is allowed. Default False
        recreate_views: if views should be recreated. Default False
        multiprocessing_mode: if multiprocessing mode is on it will patch the motor client to use process's event loop. Default False
        skip_indexes: if you want to skip working with the indexes. Default False
    """
    await init_beanie(
        database=database,
        connection_string=connection_string,
        document_models=document_models,
        allow_index_dropping=allow_index_dropping,
        recreate_views=recreate_views,
        multiprocessing_mode=multiprocessing_mode,
        skip_indexes=skip_indexes,
    )
    await asyncio.gather(
        *(_set_jsonschema_validator(database, model) for model in document_models)
    )


def get_mongodb(url: str, name: str) -> AsyncIOMotorDatabase:
    """Returns a mongo db which can be used to get collections

    Args:
        url: the mongo db url
        name: the name of the mongo database

    Returns:
        a AsyncIOMotorDatabase instance that can be used to extract collections
    """
    global _CONNECTIONS

    try:
        client = _CONNECTIONS[url]
        if client.io_loop.is_closed():
            client.close()
            logger.debug("Re-opened mongo db connection")
            client = AsyncIOMotorClient(url, tz_aware=True)
    except KeyError:
        logger.debug("New mongo db connection initialized")
        client = AsyncIOMotorClient(url, tz_aware=True)

    _CONNECTIONS[url] = client
    return client[name]


async def find_one(
    collection: AsyncIOMotorCollection,
    _filter: Dict[str, Any],
    dropped_fields: Tuple[str, ...] = (),
    sorted_by: Optional[List[Tuple[str, int]]] = None,
    schema: Type[ModelOrDict] = dict,
) -> ModelOrDict:
    """Finds first record in the given collection that matches the given _filter

    Args:
        collection: the mongodb collection to find the record
        _filter: the object which the returned record should match against
        dropped_fields: fields to be dropped from the returned record
        sorted_by: List of (field, sort-direction) tuples to use in sorting
        schema: the type the record should conform to

    Returns:
        a dict representing the given record

    Raises:
        NotFoundError: no matches for '{_filter}'
        ValidationError: the document does not satisfy the schema passed
    """
    projection = {k: False for k in dropped_fields}
    kwargs = dict(projection=projection, filter=_filter)

    if sorted_by:
        kwargs["sort"] = sorted_by

    document = await collection.find_one(**kwargs)
    if document is None:
        raise NotFoundError(f"no matches for '{_filter}'")

    return parse_record(schema, document)


async def find(
    collection: AsyncIOMotorCollection,
    filters: Optional[dict] = None,
    exclude: Tuple[str] = (),
    limit: Optional[int] = None,
    skip: int = 0,
    sort: Optional[Sequence[str]] = None,
    schema: Type[ModelOrDict] = dict,
    skip_validation: bool = False,
) -> List[ModelOrDict]:
    """Retrieves all records in the collection up to limit records, given the sort order

    It automatically ignores any records that don't follow the given schema.
    If you need a proper validation failure if there are records that are in improper structure,
    set 'skip_validation'

    Args:
        collection: the mongo db collection to query from
        filters: the mongodb like filters which all returned records should satisfy
        exclude: the fields to exclude
        limit: the maximum number of records to return: If limit is negative, all results are returned
        skip: the number of records to skip
        sort: List of fields to use in sorting, where fields starting with "-" are descending
        schema: the schema the records should conform to; default = Dict[str, Any]
        skip_validation: whether validation errors should be silently ignored; default = False

    Returns:
        a list of documents that were found

    Raises:
        ValidationError: the document does not satisfy the schema passed
    """
    projection = {field: 0 for field in exclude}

    if filters is None:
        filters = {}

    db_cursor = collection.find(filters, projection).skip(skip)
    if sort:
        sort_config = extract_sort_config(sort)
        db_cursor.sort(sort_config)

    if limit and limit >= 0:
        db_cursor.limit(limit)

    response = []
    async for item in db_cursor:
        try:
            parsed_item = parse_record(schema, item)
            response.append(parsed_item)
        except ValidationError as exp:
            if not skip_validation:
                raise exp

    return response


async def insert_one(collection: AsyncIOMotorCollection, document: Dict[str, Any]):
    """Inserts one document into the given collection

    Args:
        collection: the mongo AsyncIOMotorCollection to insert the documents into
        document: the dictionary to insert into the collection

    Returns:
        the inserted document

    Raises:
        DatabaseError: server failed to insert document
    """
    result = await collection.insert_one(document)
    if result.acknowledged:
        document["_id"] = str(result.inserted_id)
        return document

    raise DatabaseError("server failed to insert document")


async def insert_one_if_not_exists(
    collection: AsyncIOMotorCollection,
    document: Dict[str, Any],
    unique_fields: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """Inserts a given document in the given collection if it does not exist

    Args:
        collection: the mongo AsyncIOMotorCollection to insert the documents into
        document: the dictionary to insert into the collection
        unique_fields: the tuple of properties that constitute a composite primary key

    Returns:
        the inserted document

    Raises:
        DatabaseError: server failed to replace or insert document
    """
    _filter = _extract_filter_obj(document=document, unique_fields=unique_fields)
    doc_exists = await collection.count_documents(_filter, limit=1) == 1

    if not doc_exists:
        return await insert_one(collection=collection, document=document)


async def update_many(
    collection: AsyncIOMotorCollection,
    _filter: dict,
    payload: Dict[str, Any],
):
    """Updates many documents in the given collection for the given filter

    Args:
        collection: the mongo AsyncIOMotorCollection to insert the documents into
        _filter: the filter for the documents
        payload: the partial dict to update the documents

    Returns:
        the number of documents that were modified

    Raises:
        DatabaseError: server failed updating documents
        NotFoundError: no matches for {filter}
    """
    update = {"$set": {**payload, "updated_at": get_current_timestamp()}}
    result = await collection.update_many(filter=_filter, update=update)

    if not result.acknowledged:
        raise DatabaseError("server failed updating documents")

    if result.matched_count == 0:
        raise NotFoundError(f"no matches for {_filter}")

    return result.modified_count


async def update_one(
    collection: AsyncIOMotorCollection,
    _filter: dict,
    payload: Dict[str, Any],
    return_document: bool = ReturnDocument.BEFORE,
    upsert: bool = False,
) -> Mapping[str, Any]:
    """Updates one document in the given collection for the given filter

    Args:
        collection: the mongo AsyncIOMotorCollection to insert the documents into
        _filter: the filter for the documents
        payload: the partial dict to update the documents
        return_document:  If ReturnDocument.BEFORE (the default), returns the original document before it was updated.
            If ReturnDocument.AFTER, returns the updated or inserted document.
        upsert: whether we should insert the document if it does not exist

    Returns:
        either the modified document or the original document

    Raises:
        NotFoundError: no matches for {filter}
    """
    update = {"$set": {**payload, "updated_at": get_current_timestamp()}}
    result = await collection.find_one_and_update(
        filter=_filter,
        update=update,
        return_document=return_document,
        upsert=upsert,
    )

    if result is None:
        raise NotFoundError(f"no matches for {_filter}")

    return result


async def delete_many(collection: AsyncIOMotorCollection, _filter: dict):
    """Deletes many documents in the given collection for the given filter

    Args:
        collection: the mongo AsyncIOMotorCollection to insert the documents into
        _filter: the filter for the documents

    Returns:
        the number of documents that were deleted

    Raises:
        DatabaseError: server failed deleting documents
        NotFoundError: no matches for {filter}
    """
    result = await collection.delete_many(filter=_filter)

    if not result.acknowledged:
        raise DatabaseError("server failed deleting documents")

    if result.deleted_count == 0:
        raise NotFoundError(f"no matches for {_filter}")

    return result.deleted_count


def extract_sort_config(sort_fields: Sequence[str]) -> List[Tuple[str, SortDirection]]:
    """Gets the configuration for sorting basing on sort_fields passed

    Sort fields are passed as prefixed with a "-" if a descending sort is required,
    otherwise, their names are just listed.

    Args:
        sort_fields: the fields to sort by, prefixed with "-" if descending sort is needed

    Returns:
        The list of tuples of field and direction
    """
    sort_config: List[Tuple[str, SortDirection]] = []

    for sort_field in sort_fields:
        if sort_field.startswith("-"):
            sort_config.append((sort_field[1:], SortDirection.DESCENDING))
        else:
            sort_config.append((sort_field, SortDirection.ASCENDING))

    return sort_config


def _extract_filter_obj(document: Dict[str, Any], unique_fields: Tuple[str, ...]):
    """Extracts a filter object from a document, given a set of unique fields

    Args:
        document: the dict from which to construct the filter object
        unique_fields: a tuple of fields that together constitute a unique composite key for the document

    Returns:
        a dict that can be used to find the given document within a mongodb collection

    Raises:
        DatabaseError: property '{unique_field_name}' is required
    """
    try:
        return {k: document[k] for k in unique_fields}
    except KeyError as exp:
        raise DatabaseError(f"property '{exp}' is required")


async def _set_jsonschema_validator(
    database: AsyncIOMotorDatabase, model: type[Document]
):
    """Makes the collection of the given model reject documents that violate its schema

    Args:
        database: motor database instance
        model: model class
    """
    name = model.get_settings().name
    # collMod fails on a collection that does not exist yet e.g. one without indexes
    if name not in await database.list_collection_names(filter={"name": name}):
        with suppress(CollectionInvalid):
            await database.create_collection(name)

    await database.command(
        {
            "collMod": name,
            "validator": _get_jsonschema_validator(model),
            "validationLevel": "strict",
            "validationAction": "error",
        }
    )


def _get_jsonschema_validator(model: type[Document]) -> dict:
    """Gets the JSONSchema validator for the given model.

    It cleans up the JSONSchema to be mongoDB validator-ready

    Args:
        model: model class

    Returns:
        the JSONSchema for mongodb collection
    """
    json_schema = model.model_json_schema()
    definitions = json_schema.get("$defs", {})
    is_extra_allow = model.model_config.get("extra") == "allow"

    return {
        "$jsonSchema": {
            **_to_mongo_json_schema(json_schema, definitions=definitions),
            "additionalProperties": is_extra_allow,
        }
    }


def _to_mongo_json_schema(value: Any, definitions: Dict[str, Any]) -> Any:
    """Converts a pydantic JSON schema to mongodb's dialect of JSON schema

    Mongodb supports neither references nor annotations like 'default' and 'format',
    and it validates BSON types, so dates and ObjectIds are not the strings JSON sees.

    Args:
        value: the JSON schema or a part of it
        definitions: the '$defs' of the root JSON schema, which '$ref's point to

    Returns:
        the mongodb-ready JSON schema
    """
    if isinstance(value, list):
        return [_to_mongo_json_schema(item, definitions) for item in value]

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
    elif json_type == "string" and schema.get("pattern") == _OBJECT_ID_PATTERN:
        schema = {"bsonType": "objectId"}
    elif json_type is not None:
        schema["bsonType"] = _JSON_TO_BSON_TYPES[json_type]

    result = {}
    for key, item in schema.items():
        if key not in _MONGO_JSON_SCHEMA_KEYWORDS:
            continue

        if key in ("properties", "patternProperties"):
            result[key] = {
                k: _to_mongo_json_schema(v, definitions) for k, v in item.items()
            }
        else:
            result[key] = _to_mongo_json_schema(item, definitions)

    return result
