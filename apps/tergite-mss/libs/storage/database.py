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
from .base.query import ALL, Filter, Page, Sort, extract_fields
from .base.schema import Schema, StorageSpec, is_list_field, resolve_field
from .base.store import DbStore
from .base.update import Returning, Update

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
        where: Filter = ALL,
        sort: Sequence[Sort] = (),
        page: Page = Page(),
    ) -> List[T]:
        self.__ensure_known(schema, where=where, sort=sort)
        return await self.__db_store.find(schema, where=where, sort=sort, page=page)

    async def find_one(
        self, schema: Type[T], where: Filter = ALL, sort: Sequence[Sort] = ()
    ) -> Optional[T]:
        records = await self.find(schema, where=where, sort=sort, page=Page(limit=1))
        return records[0] if records else None

    async def count(self, schema: Type[T], where: Filter = ALL) -> int:
        self.__ensure_known(schema, where=where)
        return await self.__db_store.count(schema, where=where)

    async def find_distinct(
        self, schema: Type[T], field: str, where: Filter = ALL
    ) -> List[Any]:
        """Gets the different values the field holds in the matched records"""
        self.__ensure_known(schema, where=where, fields=(field,))
        return await self.__db_store.find_distinct(schema, field, where=where)

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
        where: Filter,
        changes: Sequence[Update],
        *,
        should_upsert: bool = False,
        returning: Returning = Returning.AFTER,
    ) -> Optional[T]:
        """Updates the first matched record

        Returns:
            the record before or after the update, or None if none matched and none was
            upserted
        """
        self.__ensure_known(schema, where=where, changes=changes)
        return await self.__db_store.update_one(
            schema,
            where=where,
            changes=changes,
            should_upsert=should_upsert,
            returning=returning,
        )

    async def update_many(
        self, schema: Type[T], where: Filter, changes: Sequence[Update]
    ) -> int:
        """Updates every matched record, returning how many changed"""
        self.__ensure_known(schema, where=where, changes=changes)
        return await self.__db_store.update_many(schema, where=where, changes=changes)

    async def delete_one(self, schema: Type[T], where: Filter) -> Optional[T]:
        """Deletes the first matched record, returning it, or None if none matched"""
        self.__ensure_known(schema, where=where)
        return await self.__db_store.delete_one(schema, where=where)

    async def delete_many(self, schema: Type[T], where: Filter) -> int:
        """Deletes every matched record, returning how many were deleted"""
        self.__ensure_known(schema, where=where)
        return await self.__db_store.delete_many(schema, where=where)

    async def close(self) -> None:
        await self.__db_store.close()

    def __ensure_known(
        self,
        schema: Type[T],
        where: Filter = ALL,
        sort: Sequence[Sort] = (),
        changes: Sequence[Update] = (),
        fields: Sequence[str] = (),
    ) -> Type[T]:
        if schema not in self.__schemas:
            raise UnknownSchemaError(f"{schema.__name__} is not in this Database")

        named_fields = (
            *extract_fields(where),
            *(item.field for item in sort),
            *(item.field for item in changes),
            *fields,
        )
        for field in named_fields:
            resolve_field(schema, field)
        return schema


def _create_store(database_url: str, schemas: Sequence[Type[Schema]]) -> DbStore:
    scheme = urlsplit(database_url).scheme
    if scheme in ("mongodb", "mongodb+srv"):
        from .mongo import MongoStore  # each backend's driver loads only when used

        return MongoStore(database_url, schemas)
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
