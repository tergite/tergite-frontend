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
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type

import pymongo
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pydantic import ValidationError
from pymongo import ReturnDocument

from .date_time import get_current_timestamp
from .exc import NotFoundError
from .models import ModelOrDict, parse_record

_CONNECTIONS = {}


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
            logging.debug(
                f"New mongo db connection at {datetime.now(timezone.utc).isoformat()}"
            )
            client = AsyncIOMotorClient(url, tz_aware=True)
    except KeyError:
        logging.debug(
            f"New mongo db connection at {datetime.now(timezone.utc).isoformat()}"
        )
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
    sort: Optional[List[str]] = None,
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
        sort_config = _extract_sort_config(sort)
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
        ValueError: server failed to insert document
    """
    result = await collection.insert_one(document)
    if result.acknowledged:
        document["_id"] = str(result.inserted_id)
        return document

    raise ValueError("server failed to insert document")


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
        ValueError: server failed to replace or insert document
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
        ValueError: server failed updating documents
        NotFoundError: no matches for {filter}
    """
    update = {"$set": {**payload, "updated_at": get_current_timestamp()}}
    result = await collection.update_many(filter=_filter, update=update)

    if not result.acknowledged:
        raise ValueError("server failed updating documents")

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
        ValueError: server failed deleting documents
        NotFoundError: no matches for {filter}
    """
    result = await collection.delete_many(filter=_filter)

    if not result.acknowledged:
        raise ValueError("server failed deleting documents")

    if result.deleted_count == 0:
        raise NotFoundError(f"no matches for {_filter}")

    return result.deleted_count


def _extract_filter_obj(document: Dict[str, Any], unique_fields: Tuple[str, ...]):
    """Extracts a filter object from a document, given a set of unique fields

    Args:
        document: the dict from which to construct the filter object
        unique_fields: a tuple of fields that together constitute a unique composite key for the document

    Returns:
        a dict that can be used to find the given document within a mongodb collection

    Raises:
        ValueError: property '{unique_field_name}' is required
    """
    try:
        return {k: document[k] for k in unique_fields}
    except KeyError as exp:
        raise ValueError(f"property '{exp}' is required")


def _extract_sort_config(sort_fields: List[str]) -> List[Tuple[str, int]]:
    """Gets the configuration for sorting basing on sort_fields passed

    Sort fields are passed as prefixed with a "-" if a descending sort is required,
    otherwise, their names are just listed.

    Args:
        sort_fields: the fields to sort by, prefixed with "-" if descending sort is needed

    Returns:
        The list of tuples of field and direction
    """
    sort_config: List[Tuple[str, int]] = []

    for sort_field in sort_fields:
        if sort_field.startswith("-"):
            sort_config.append((sort_field[1:], pymongo.DESCENDING))
        else:
            sort_config.append((sort_field, pymongo.ASCENDING))

    return sort_config
