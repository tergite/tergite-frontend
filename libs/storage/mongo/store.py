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

"""MongoStore: the DbStore for MongoDB, on PyMongo's async client"""

from contextlib import contextmanager, suppress
from datetime import datetime, timezone
from functools import partial
from typing import Any, Dict, Iterator, List, Optional, Sequence, Type, TypeVar

import pymongo.errors
from bson import ObjectId
from pymongo import AsyncMongoClient, IndexModel, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.collation import Collation

from ..base.exc import DuplicateKeyError, StorageError
from ..base.query import Filter, extract_fields
from ..base.schema import Schema, read_stored
from ..base.store import DbStore
from ..base.update import Returning, Update
from .schema import CASE_INSENSITIVE, get_indexes, get_validator
from .translate import (
    convert_to_document,
    convert_to_record,
    get_document_field,
    translate_filter,
    translate_sort,
    translate_update,
)

T = TypeVar("T", bound=Schema)
_DUPLICATE_KEY_CODE = 11000
_INDEX_NOT_FOUND_CODE = 27
_NAMESPACE_EXISTS_CODE = 48
_INDEX_OPTIONS = ("unique", "expireAfterSeconds", "sparse")


class MongoStore(DbStore):
    """Stores each schema in the collection its `__storage__` names

    The database is the one the URL names, as in `mongodb://host:27017/tergite`.
    """

    def __init__(self, database_url: str, schemas: Sequence[Type[Schema]]):
        self._client = AsyncMongoClient(database_url, tz_aware=True)
        try:
            self._database = self._client.get_default_database()
        except pymongo.errors.ConfigurationError as exp:
            raise StorageError(f"the MongoDB URL names no database: {exp}") from exp
        self._schemas = tuple(schemas)

    async def setup(self) -> None:
        # one at a time: concurrently, each opens a pooled connection that is never closed
        """Creates what the schemas need, such as tables and indexes; safe to repeat"""
        for schema in self._schemas:
            await self._set_up_collection(schema)

    async def get(self, schema: Type[T], key: Any) -> Optional[T]:
        """Gets the unexpired record of the given key

        Args:
            schema: the schema of the record
            key: the value of the schema's key field

        Returns:
            the record, or None if there is none
        """
        key_field = schema.__storage__.key
        document = await self._get_collection(schema).find_one(
            _translate_unexpired_filter(schema, {key_field: key})
        )
        if document is None:
            return None
        return read_stored(schema, document, partial(convert_to_record, schema))

    async def find(
        self,
        schema: Type[T],
        query_filter: Filter,
        sort: Sequence[str],
        skip: int,
        limit: Optional[int],
    ) -> List[T]:
        """Finds the unexpired records that match the filter, in the sort's order

        Args:
            schema: the schema of the records
            query_filter: the filter, as `Database.find` takes it
            sort: the fields to sort by; a leading '-' sorts descending
            skip: the number of matched records to skip
            limit: the most records to return; None returns all

        Returns:
            the matched records
        """
        cursor = self._get_collection(schema).find(
            _translate_unexpired_filter(schema, query_filter),
            sort=translate_sort(sort) or None,
            skip=skip,
            limit=limit or 0,
            collation=_get_query_collation(schema, query_filter),
        )
        records = [
            read_stored(schema, document, partial(convert_to_record, schema))
            async for document in cursor
        ]
        return [record for record in records if record is not None]

    async def count(self, schema: Type[T], query_filter: Filter) -> int:
        """Counts the unexpired records that match the filter

        Args:
            schema: the schema of the records
            query_filter: the filter, as `Database.find` takes it

        Returns:
            the number of matched records
        """
        options = _get_collation_option(schema, query_filter)
        return await self._get_collection(schema).count_documents(
            _translate_unexpired_filter(schema, query_filter), **options
        )

    async def find_distinct(
        self, schema: Type[T], field: str, query_filter: Filter
    ) -> List[Any]:
        """Gets the different values the field holds in the matched records

        Args:
            schema: the schema of the records
            field: the field, dotted for a nested one
            query_filter: the filter, as `Database.find` takes it

        Returns:
            the distinct values
        """
        values = await self._get_collection(schema).distinct(
            get_document_field(field),
            _translate_unexpired_filter(schema, query_filter),
            **_get_collation_option(schema, query_filter),
        )
        return [
            str(value) if isinstance(value, ObjectId) else value for value in values
        ]

    async def insert(self, schema: Type[T], record: T) -> T:
        """Inserts the record

        Args:
            schema: the schema of the record
            record: the record to insert

        Returns:
            the inserted record

        Raises:
            DuplicateKeyError: a unique field's value is taken
        """
        with _translate_duplicate_key_errors():
            await self._get_collection(schema).insert_one(
                convert_to_document(schema, record)
            )
        return record

    async def insert_many(self, schema: Type[T], records: Sequence[T]) -> List[T]:
        """Inserts the records

        Args:
            schema: the schema of the records
            records: the records to insert

        Returns:
            the inserted records

        Raises:
            DuplicateKeyError: a unique field's value is taken
        """
        if len(records) == 0:
            return []
        with _translate_duplicate_key_errors():
            await self._get_collection(schema).insert_many(
                [convert_to_document(schema, record) for record in records]
            )
        return list(records)

    async def update_one(
        self,
        schema: Type[T],
        query_filter: Filter,
        update: Update,
        should_upsert: bool,
        returning: Returning,
    ) -> Optional[T]:
        """Updates the first matched record

        Args:
            schema: the schema of the record
            query_filter: the filter, as `Database.find` takes it
            update: the update, as `Database.update_one` takes it
            should_upsert: whether to create the record if none matched
            returning: whether to return the record as it was before or after the update

        Returns:
            the record before or after the update, or None if none matched and none was
            upserted

        Raises:
            DuplicateKeyError: a unique field's value is taken
        """
        return_document = (
            ReturnDocument.BEFORE
            if returning == Returning.BEFORE
            else ReturnDocument.AFTER
        )
        with _translate_duplicate_key_errors():
            document = await self._get_collection(schema).find_one_and_update(
                _translate_unexpired_filter(schema, query_filter),
                translate_update(schema, update),
                upsert=should_upsert,
                return_document=return_document,
                **_get_collation_option(schema, query_filter),
            )
        return None if document is None else convert_to_record(schema, document)

    async def update_many(
        self, schema: Type[T], query_filter: Filter, update: Update
    ) -> int:
        """Updates every matched record

        Args:
            schema: the schema of the records
            query_filter: the filter, as `Database.find` takes it
            update: the update, as `Database.update_one` takes it

        Returns:
            the number of records changed

        Raises:
            DuplicateKeyError: a unique field's value is taken
        """
        with _translate_duplicate_key_errors():
            result = await self._get_collection(schema).update_many(
                _translate_unexpired_filter(schema, query_filter),
                translate_update(schema, update),
                **_get_collation_option(schema, query_filter),
            )
        return result.modified_count

    async def delete_one(self, schema: Type[T], query_filter: Filter) -> Optional[T]:
        """Deletes the first matched record

        Args:
            schema: the schema of the record
            query_filter: the filter, as `Database.find` takes it

        Returns:
            the deleted record, or None if none matched
        """
        document = await self._get_collection(schema).find_one_and_delete(
            _translate_unexpired_filter(schema, query_filter),
            **_get_collation_option(schema, query_filter),
        )
        return None if document is None else convert_to_record(schema, document)

    async def delete_many(self, schema: Type[T], query_filter: Filter) -> int:
        """Deletes every matched record

        Args:
            schema: the schema of the records
            query_filter: the filter, as `Database.find` takes it

        Returns:
            the number of records deleted
        """
        result = await self._get_collection(schema).delete_many(
            _translate_unexpired_filter(schema, query_filter),
            **_get_collation_option(schema, query_filter),
        )
        return result.deleted_count

    async def close(self) -> None:
        """Closes the connections to the database"""
        await self._client.close()

    def _get_collection(self, schema: Type[Schema]) -> AsyncCollection:
        return self._database[schema.__storage__.table]

    async def _set_up_collection(self, schema: Type[Schema]) -> None:
        name = schema.__storage__.table
        # collMod fails on a collection that does not exist yet; another process may
        # create it first
        with (
            suppress(pymongo.errors.CollectionInvalid),
            _ignore_code(_NAMESPACE_EXISTS_CODE),
        ):
            await self._database.create_collection(name)

        await self._database.command(
            {
                "collMod": name,
                "validator": get_validator(schema),
                # checks every insert, and every update of a document that is valid already,
                # so that documents written before the validator can still be updated
                "validationLevel": "moderate",
                "validationAction": "error",
            }
        )
        await _sync_indexes(self._get_collection(schema), get_indexes(schema))


def _translate_unexpired_filter(
    schema: Type[Schema], query_filter: Filter
) -> Dict[str, Any]:
    """Translates the filter, leaving out records past their expiry

    The TTL monitor deletes them only about once a minute, and a store reads none.
    """
    query = translate_filter(schema, query_filter)
    expires_field = schema.__storage__.expires
    if expires_field is None:
        return query
    is_unexpired = {
        "$or": [
            {expires_field: None},
            {expires_field: {"$gt": datetime.now(timezone.utc)}},
        ]
    }
    return {"$and": [query, is_unexpired]} if query else is_unexpired


async def _sync_indexes(collection: AsyncCollection, indexes: List[IndexModel]) -> None:
    """Creates the indexes, first dropping any of the same name whose options differ"""
    existing = {info["name"]: info async for info in await collection.list_indexes()}
    for index in indexes:
        wanted = index.document
        current = existing.get(wanted["name"])
        if current is not None and not _is_same_index(current, wanted):
            # another process setting up may drop it first
            with _ignore_code(_INDEX_NOT_FOUND_CODE):
                await collection.drop_index(wanted["name"])
    if indexes:
        await collection.create_indexes(indexes)


def _is_same_index(current: Dict[str, Any], wanted: Dict[str, Any]) -> bool:
    if list(current["key"].items()) != list(wanted["key"].items()):
        return False
    if any(current.get(option) != wanted.get(option) for option in _INDEX_OPTIONS):
        return False
    return _get_collation_key(current.get("collation")) == _get_collation_key(
        wanted.get("collation")
    )


def _get_collation_key(collation: Any) -> Optional[tuple]:
    if collation is None:
        return None
    document = collation.document if isinstance(collation, Collation) else collation
    return document.get("locale"), document.get("strength")


def _get_query_collation(
    schema: Type[Schema], query_filter: Filter
) -> Optional[Collation]:
    """The collation a query on case-insensitive fields needs to use their index"""
    fields = set(extract_fields(query_filter))
    is_case_insensitive = bool(fields & set(schema.__storage__.case_insensitive))
    return CASE_INSENSITIVE if is_case_insensitive else None


def _get_collation_option(schema: Type[Schema], query_filter: Filter) -> Dict[str, Any]:
    collation = _get_query_collation(schema, query_filter)
    return {} if collation is None else {"collation": collation}


@contextmanager
def _translate_duplicate_key_errors() -> Iterator[None]:
    """Turns MongoDB's duplicate key errors into the storage layer's own"""
    try:
        yield
    except pymongo.errors.DuplicateKeyError as exp:
        raise DuplicateKeyError(str(exp)) from exp
    except pymongo.errors.BulkWriteError as exp:
        if any(
            error.get("code") == _DUPLICATE_KEY_CODE
            for error in exp.details.get("writeErrors", [])
        ):
            raise DuplicateKeyError(str(exp)) from exp
        raise


@contextmanager
def _ignore_code(code: int) -> Iterator[None]:
    """Ignores MongoDB's failures of the given code"""
    try:
        yield
    except pymongo.errors.OperationFailure as exp:
        if exp.code != code:
            raise
