# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Test utilities for mongodb"""
from types import MappingProxyType
from typing import Any, Dict, List, Optional, Sequence, Type, TypeVar

import pymongo.database
from beanie import Document, PydanticObjectId
from bson import ObjectId
from pymongo import ReturnDocument, collection, database, errors


def find_in_collection(
    database: pymongo.database.Database,
    collection_name: str,
    fields_to_exclude: Sequence[str] = (),
    _filter: Dict[str, Any] = MappingProxyType({}),
) -> List[Dict[str, Any]]:
    """Gets the list of all records that match the given filter in the database

    Args:
        database: the mongodb database where to get the records from
        collection_name: the name of the collection to get the records from
        fields_to_exclude: the fields to exclude from the returned records
        _filter: the mongo-like filter object

    Returns:
        a list of dicts that represent the records, ignoring "_id" and "ti
    """
    return list(
        database[collection_name].find(
            dict(_filter), {k: False for k in fields_to_exclude}
        )
    )


def insert_in_collection(
    database: pymongo.database.Database,
    collection_name: str,
    data: List[Dict[str, Any]],
) -> List[ObjectId]:
    """Inserts the records into the db

    Args:
        database: the mongodb database where to insert the record
        collection_name: the name of the collection to insert them into
        data: the list of records to insert

    Returns:
        list of ids of inserted documents
    """
    result = database[collection_name].insert_many(
        [
            {k: ObjectId(v) if k == "_id" else v for k, v in item.items()}
            for item in data
        ]
    )
    return result.inserted_ids


T = TypeVar("T", bound=Document)


def insert_if_not_exist(db: database.Database, schema: Type[T], data: Dict[str, Any]):
    """Inserts a given auth document into the database if it does not exist

    Args:
        db: The pymongo.database.Database instance to insert into
        schema: the beanie.Document schema corresponding to the collection to which to insert into
        data: the document to insert
    """
    try:
        col: collection.Collection = db[_get_collection_name(schema)]
        col.insert_one(data)
    except errors.DuplicateKeyError:
        pass


def get_db_record(
    db: database.Database,
    schema: Type[T],
    _id: Optional[str] = None,
    _filter: Optional[dict] = None,
) -> Optional[dict]:
    """Gets a given auth document from the database or None if it does not exist"""
    col: collection.Collection = db[_get_collection_name(schema)]
    filter_obj = {"_id": PydanticObjectId(_id)} if _id else {}
    if _filter is not None:
        filter_obj.update(_filter)
    return col.find_one(filter_obj)


def update_db_record(
    db: database.Database,
    schema: Type[T],
    _id: Optional[str] = None,
    _filter: Optional[dict] = None,
    update: Optional[dict] = None,
) -> Optional[dict]:
    """Updates the given auth document"""
    col: collection.Collection = db[_get_collection_name(schema)]
    filter_obj = {"_id": PydanticObjectId(_id)} if _id else {}
    if _filter is not None:
        filter_obj.update(_filter)
    payload = update if isinstance(update, dict) else {}
    return col.find_one_and_update(
        filter_obj, payload, return_document=ReturnDocument.AFTER
    )


def _get_collection_name(schema: Type[T]) -> str:
    """The collection of a storage Schema or of a beanie Document"""
    storage = getattr(schema, "__storage__", None)
    return storage.table if storage is not None else schema.Settings.name
