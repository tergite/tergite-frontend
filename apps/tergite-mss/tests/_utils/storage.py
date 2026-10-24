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
"""Test utilities for the databases the storage layer runs on

The storage tests get a database of each kind per test. The API tests share one of each
kind for the session, as the app they run on does, apart from the storage tests', which drop
theirs; a synchronous test reaches it through a SyncDatabase.
"""
import asyncio
import threading
from pathlib import Path
from typing import Any, Coroutine, List, Mapping, Optional, Sequence, Type, TypeVar
from urllib.parse import urlsplit, urlunsplit

from pymongo import AsyncMongoClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from libs.storage import Database, DuplicateKeyError, Filter, Schema, Update
from tests._utils.env import TEST_DB_NAME, TEST_MONGODB_URL, TEST_POSTGRES_URL

SQL_DATABASE_KINDS = ("postgresql", "sqlite")
DATABASE_KINDS = ("mongodb", *SQL_DATABASE_KINDS)
_MONGODB_NAME = "tergite-storage-test"
_API_POSTGRES_NAME = "tergite_api_test"

T = TypeVar("T", bound=Schema)


class SyncDatabase:
    """A Database driven from synchronous tests, on an event loop of its own thread"""

    def __init__(self, database_url: str, schemas: Sequence[Type[Schema]]):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self.database = Database(database_url, schemas=schemas)
        self.run(self.database.setup())

    def get(self, schema: Type[T], key: Any) -> Optional[T]:
        return self.run(self.database.get(schema, key))

    def find(
        self,
        schema: Type[T],
        filter: Optional[Filter] = None,
        sort: Sequence[str] = (),
    ) -> List[T]:
        return self.run(self.database.find(schema, filter=filter, sort=sort))

    def find_one(self, schema: Type[T], filter: Filter) -> Optional[T]:
        return self.run(self.database.find_one(schema, filter))

    def count(self, schema: Type[T], filter: Optional[Filter] = None) -> int:
        return self.run(self.database.count(schema, filter=filter))

    def insert(self, schema: Type[T], record: T) -> T:
        return self.run(self.database.insert(schema, record))

    def insert_many(self, schema: Type[T], records: Sequence[T]) -> List[T]:
        return self.run(self.database.insert_many(schema, records))

    def update_one(
        self, schema: Type[T], filter: Filter, update: Update
    ) -> Optional[T]:
        return self.run(self.database.update_one(schema, filter, update))

    def update_many(self, schema: Type[T], filter: Filter, update: Update) -> int:
        return self.run(self.database.update_many(schema, filter, update))

    def delete_many(self, schema: Type[T], filter: Filter) -> int:
        return self.run(self.database.delete_many(schema, filter))

    def close(self) -> None:
        self.run(self.database.close())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()

    def run(self, coroutine: Coroutine) -> Any:
        """Runs the coroutine on the database's event loop, waiting for its result"""
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result()


def to_record(schema: Type[T], document: Mapping[str, Any]) -> T:
    """Gets the record a fixture document holds, its id named `_id` as MongoDB names it"""
    values = dict(document)
    if "_id" in values:
        values["id"] = values.pop("_id")
    return schema.model_validate(values)


def insert_if_not_exist(
    db: SyncDatabase, schema: Type[T], document: Mapping[str, Any]
) -> None:
    """Inserts the record of a fixture document, unless one of its key or unique fields is
    stored already"""
    try:
        db.insert(schema, to_record(schema, document))
    except DuplicateKeyError:
        pass


def get_api_database_url(kind: str, tmp_path: Path) -> str:
    """Gets the URL of the database of the kind that the app under test runs on"""
    if kind == "mongodb":
        return f"{TEST_MONGODB_URL.rstrip('/')}/{TEST_DB_NAME}"
    if kind == "postgresql":
        return _get_postgres_url(_API_POSTGRES_NAME)
    return f"sqlite+aiosqlite:///{tmp_path}/api.db"


async def create_api_database(database_url: str) -> None:
    """Gets the app's database ready and empty: PostgreSQL's created if it is not yet"""
    if database_url.startswith("postgresql"):
        await _create_postgres_database(_API_POSTGRES_NAME)
        await reset_sql_database(database_url)
    if database_url.startswith("mongodb"):
        client = AsyncMongoClient(TEST_MONGODB_URL)
        await client.drop_database(TEST_DB_NAME)
        await client.close()


def get_database_url(kind: str, tmp_path: Path) -> str:
    """Gets the URL of a database of the kind, in MongoDB one of its own"""
    if kind == "mongodb":
        return f"{TEST_MONGODB_URL.rstrip('/')}/{_MONGODB_NAME}"
    return get_sql_database_url(kind, tmp_path)


async def reset_database(database_url: str) -> None:
    """Empties a shared database, so the next test starts from nothing"""
    if not database_url.startswith("mongodb"):
        await reset_sql_database(database_url)
        return
    client = AsyncMongoClient(TEST_MONGODB_URL)
    await client.drop_database(_MONGODB_NAME)
    await client.close()


def get_sql_database_url(kind: str, tmp_path: Path) -> str:
    """Gets the URL of a database of the kind: the test PostgreSQL, or a new SQLite file"""
    if kind == "postgresql":
        return TEST_POSTGRES_URL
    return f"sqlite+aiosqlite:///{tmp_path}/test.db"


async def reset_sql_database(database_url: str) -> None:
    """Drops every table of a shared database, so the next test derives its own

    A SQLite file is new to each test, so only PostgreSQL needs this.
    """
    if not database_url.startswith("postgresql"):
        return
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


async def _create_postgres_database(name: str) -> None:
    engine = create_async_engine(TEST_POSTGRES_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await engine.dispose()


def _get_postgres_url(name: str) -> str:
    """Gets the URL of another database on the test PostgreSQL server"""
    return urlunsplit(urlsplit(TEST_POSTGRES_URL)._replace(path=f"/{name}"))
