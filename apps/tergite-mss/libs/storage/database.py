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

"""Database: the one object every read and write goes through"""
from typing import Any, Iterator, List, Optional, Sequence, Type, TypeVar
from urllib.parse import urlsplit

from .base.exc import StorageError, StorageSpecError, UnknownSchemaError
from .base.query import Filter, check_filter, check_sort
from .base.schema import Schema, StorageSpec, is_list_field, resolve_field
from .base.store import DbStore
from .base.update import Returning, Update, check_key_kept, check_update

T = TypeVar("T", bound=Schema)


class Database:
    """A database holding the given schemas, behind the store its URL's scheme picks

    Every schema's `__storage__` is checked against the schema here, so a mistake in one
    fails at boot rather than on a request.
    """

    def __init__(self, database_url: str, schemas: Sequence[Type[Schema]]):
        self.database_url = database_url
        self.__schemas = frozenset(schemas)
        for schema in schemas:
            _check_storage_spec(schema, self.__schemas)
        self.__db_store = _create_store(database_url, schemas)

    async def setup(self) -> None:
        """Creates what the schemas need in the database; safe to repeat"""
        await self.__db_store.setup()

    async def get(self, schema: Type[T], key: Any) -> Optional[T]:
        return await self.__db_store.get(self.__ensure_known(schema), key)

    async def find(
        self,
        schema: Type[T],
        filter: Optional[Filter] = None,
        sort: Sequence[str] = (),
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> List[T]:
        """Finds the records that match the filter, sorted, skipping and limiting them

        Args:
            schema: the schema of the records
            filter: MongoDB-style, e.g. `{"status": {"$in": ["pending", "done"]}}`; None
                matches every record
            sort: the fields to sort by; a leading '-' sorts descending
            skip: the number of matched records to skip
            limit: the most records to return; None returns all

        Raises:
            QueryError: the filter or sort is not in the storage layer's dialect
            UnknownFieldError: a field the schema does not have
        """
        self.__ensure_known(schema, filter=filter, sort=sort)
        return await self.__db_store.find(schema, filter or {}, sort, skip, limit)

    async def find_one(
        self, schema: Type[T], filter: Optional[Filter] = None, sort: Sequence[str] = ()
    ) -> Optional[T]:
        records = await self.find(schema, filter=filter, sort=sort, limit=1)
        return records[0] if records else None

    async def count(self, schema: Type[T], filter: Optional[Filter] = None) -> int:
        self.__ensure_known(schema, filter=filter)
        return await self.__db_store.count(schema, filter or {})

    async def find_distinct(
        self, schema: Type[T], field: str, filter: Optional[Filter] = None
    ) -> List[Any]:
        """Gets the different values the field holds in the matched records"""
        self.__ensure_known(schema, filter=filter)
        resolve_field(schema, field)
        return await self.__db_store.find_distinct(schema, field, filter or {})

    async def insert(self, schema: Type[T], record: T) -> T:
        """Inserts the record

        Raises:
            DuplicateKeyError: a unique field's value is taken
        """
        _ensure_instance(self.__ensure_known(schema), record)
        return await self.__db_store.insert(schema, record)

    async def insert_many(self, schema: Type[T], records: Sequence[T]) -> List[T]:
        self.__ensure_known(schema)
        for record in records:
            _ensure_instance(schema, record)
        return await self.__db_store.insert_many(schema, records)

    async def update_one(
        self,
        schema: Type[T],
        filter: Filter,
        update: Update,
        *,
        should_upsert: bool = False,
        returning: Returning = Returning.AFTER,
    ) -> Optional[T]:
        """Updates the first matched record

        Args:
            schema: the schema of the record
            filter: MongoDB-style, as `find` takes it
            update: MongoDB update operators, e.g. `{"$set": {"status": "done"}}`
            should_upsert: whether to create the record if none matched
            returning: whether to return the record as it was before or after the update

        Returns:
            the record before or after the update, or None if none matched and none was
            upserted
        """
        self.__ensure_known(schema, filter=filter, update=update)
        return await self.__db_store.update_one(
            schema, filter, update, should_upsert, returning
        )

    async def update_many(self, schema: Type[T], filter: Filter, update: Update) -> int:
        """Updates every matched record, returning how many changed"""
        self.__ensure_known(schema, filter=filter, update=update)
        return await self.__db_store.update_many(schema, filter, update)

    async def delete_one(self, schema: Type[T], filter: Filter) -> Optional[T]:
        """Deletes the first matched record, returning it, or None if none matched"""
        self.__ensure_known(schema, filter=filter)
        return await self.__db_store.delete_one(schema, filter)

    async def delete_many(self, schema: Type[T], filter: Filter) -> int:
        """Deletes every matched record, returning how many were deleted"""
        self.__ensure_known(schema, filter=filter)
        return await self.__db_store.delete_many(schema, filter)

    async def close(self) -> None:
        await self.__db_store.close()

    def __ensure_known(
        self,
        schema: Type[T],
        filter: Optional[Filter] = None,
        sort: Sequence[str] = (),
        update: Optional[Update] = None,
    ) -> Type[T]:
        if schema not in self.__schemas:
            raise UnknownSchemaError(f"{schema.__name__} is not in this Database")

        check_filter(schema, filter)
        check_sort(schema, sort)
        if update is not None:
            check_update(schema, update)
            check_key_kept(schema, filter, update)
        return schema


def _create_store(database_url: str, schemas: Sequence[Type[Schema]]) -> DbStore:
    scheme = urlsplit(database_url).scheme
    if scheme in ("mongodb", "mongodb+srv"):
        from .mongo import MongoStore  # each backend's driver loads only when used

        return MongoStore(database_url, schemas)
    if scheme in ("redis", "rediss"):
        from .redis import RedisStore

        return RedisStore(database_url, schemas)
    # SQLAlchemy names a database and its async driver, as in postgresql+asyncpg://
    if "+" in scheme:
        from .sql import SqlStore

        return SqlStore(database_url, schemas)
    raise StorageError(f"no store supports '{scheme}://' URLs")


def _check_storage_spec(schema: Type[Schema], schemas: frozenset) -> None:
    spec = getattr(schema, "__storage__", None)
    if spec is None:
        raise StorageSpecError(f"{schema.__name__} has no __storage__")

    for field in _extract_spec_fields(spec):
        resolve_field(schema, field.lstrip("-"))

    for field in spec.indexed_lists:
        if not is_list_field(resolve_field(schema, field)):
            raise StorageSpecError(f"{schema.__name__}.{field} is not a list field")

    for field, referenced in spec.references.items():
        if referenced not in schemas:
            raise StorageSpecError(
                f"{schema.__name__}.{field} references {referenced.__name__}, "
                "which is not in this Database"
            )


def _extract_spec_fields(spec: StorageSpec) -> Iterator[str]:
    yield spec.key
    for group in (*spec.unique, *spec.indexes):
        yield from (group,) if isinstance(group, str) else group
    yield from spec.case_insensitive
    yield from spec.indexed_lists
    yield from spec.references
    if spec.expires is not None:
        yield spec.expires


def _ensure_instance(schema: Type[T], record: Any) -> None:
    if not isinstance(record, schema):
        raise TypeError(f"expected a {schema.__name__}, got {type(record).__name__}")
