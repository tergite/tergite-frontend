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
"""SqlStore: the DbStore for SQL databases, on SQLAlchemy Core's async engine

Any SQLAlchemy URL with an async driver works, e.g. `postgresql+asyncpg://` or
`sqlite+aiosqlite://`. Each write runs in one transaction, with the record's child rows. On
SQLite, foreign keys are switched on and every transaction begins immediately, so a read
that precedes a write already holds the write lock.
"""
import asyncio
import contextlib
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Sequence, Type, TypeVar

from pydantic_core import to_jsonable_python
from sqlalchemy import MetaData, delete, distinct, event, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from ..base.exc import DuplicateKeyError, QueryError, StorageError
from ..base.ids import generate_id, is_id_field
from ..base.query import LOGICAL_OPERATORS, Filter, is_operator_map
from ..base.schema import Schema
from ..base.store import DbStore
from ..base.update import Returning, Update
from .tables import (
    POSITION,
    ROW_ID,
    SchemaTables,
    convert_to_column_value,
    get_child_rows,
    get_element,
    get_schema_tables,
)
from .translate import (
    Changes,
    translate_filter,
    translate_sort,
    translate_update,
)

T = TypeVar("T", bound=Schema)
_EXPIRY_SWEEP_SECONDS = 3600


class SqlStore(DbStore):
    """Stores each schema in the table its `__storage__` names, and its lists in child tables"""

    def __init__(
        self,
        database_url: str,
        schemas: Sequence[Type[Schema]],
        expiry_sweep_seconds: float = _EXPIRY_SWEEP_SECONDS,
    ):
        self._engine = create_async_engine(database_url)
        self._metadata = MetaData()
        self._schema_tables = get_schema_tables(self._metadata, schemas)
        self._expiry_sweep_seconds = expiry_sweep_seconds
        self._expiry_sweeper: Optional[asyncio.Task] = None
        if self._engine.dialect.name == "sqlite":
            _set_up_sqlite(self._engine.sync_engine)

    async def setup(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(self._metadata.create_all)
        is_any_expiring = any(
            tables.schema.__storage__.expires for tables in self._schema_tables.values()
        )
        if is_any_expiring and self._expiry_sweeper is None:
            self._expiry_sweeper = asyncio.create_task(self._delete_expired_records())

    async def get(self, schema: Type[T], key: Any) -> Optional[T]:
        tables = self._schema_tables[schema]
        key_filter = {schema.__storage__.key: key}
        async with self._engine.connect() as conn:
            records = await _find_records(conn, tables, key_filter, limit=1)
        return records[0] if records else None

    async def find(
        self,
        schema: Type[T],
        query_filter: Filter,
        sort: Sequence[str],
        skip: int,
        limit: Optional[int],
    ) -> List[T]:
        tables = self._schema_tables[schema]
        async with self._engine.connect() as conn:
            return await _find_records(conn, tables, query_filter, sort, skip, limit)

    async def count(self, schema: Type[T], query_filter: Filter) -> int:
        tables = self._schema_tables[schema]
        statement = (
            select(func.count())
            .select_from(tables.table)
            .where(translate_filter(tables, query_filter))
        )
        async with self._engine.connect() as conn:
            return await conn.scalar(statement)

    async def find_distinct(
        self, schema: Type[T], field: str, query_filter: Filter
    ) -> List[Any]:
        tables = self._schema_tables[schema]
        where = translate_filter(tables, query_filter)
        list_table = tables.list_tables.get(field)
        if list_table is not None and list_table.element_model is not None:
            raise QueryError(
                f"'{field}' is a list of models, which has no distinct values"
            )
        if list_table is None:
            statement = select(distinct(tables.table.c[field])).where(where)
        else:
            parent_keys = select(tables.table.c[schema.__storage__.key]).where(where)
            child = list_table.table
            statement = select(distinct(child.c[list_table.value_column])).where(
                child.c[list_table.parent_column].in_(parent_keys)
            )
        async with self._engine.connect() as conn:
            return list(await conn.scalars(statement))

    async def insert(self, schema: Type[T], record: T) -> T:
        tables = self._schema_tables[schema]
        with _translate_unique_violations():
            async with self._engine.begin() as conn:
                await _insert_record(conn, tables, record)
        return record

    async def insert_many(self, schema: Type[T], records: Sequence[T]) -> List[T]:
        tables = self._schema_tables[schema]
        with _translate_unique_violations():
            async with self._engine.begin() as conn:
                for record in records:
                    await _insert_record(conn, tables, record)
        return list(records)

    async def update_one(
        self,
        schema: Type[T],
        query_filter: Filter,
        update: Update,
        should_upsert: bool,
        returning: Returning,
    ) -> Optional[T]:
        tables = self._schema_tables[schema]
        changes = translate_update(tables, update)
        with _translate_unique_violations():
            async with self._engine.begin() as conn:
                key = await _find_first_key(conn, tables, query_filter)
                if key is None and not should_upsert:
                    return None
                if key is None:
                    key = await _insert_upserted_record(
                        conn, tables, query_filter, update
                    )
                    if returning == Returning.BEFORE:
                        return None
                    return await _get_record(conn, tables, key)

                before = await _get_record(conn, tables, key)
                await _write_changes(conn, tables, key, changes)
                if returning == Returning.BEFORE:
                    return before
                return await _get_record(conn, tables, key)

    async def update_many(
        self, schema: Type[T], query_filter: Filter, update: Update
    ) -> int:
        tables = self._schema_tables[schema]
        changes = translate_update(tables, update)
        with _translate_unique_violations():
            async with self._engine.begin() as conn:
                before = await _find_records(
                    conn, tables, query_filter, should_lock=True
                )
                for record in before:
                    key = getattr(record, schema.__storage__.key)
                    await _write_changes(conn, tables, key, changes)
                keys = [getattr(record, schema.__storage__.key) for record in before]
                after = await _find_records(
                    conn, tables, {schema.__storage__.key: {"$in": keys}}
                )
        after_by_key = {
            getattr(record, schema.__storage__.key): record for record in after
        }
        return sum(
            1
            for record in before
            if after_by_key.get(getattr(record, schema.__storage__.key)) != record
        )

    async def delete_one(self, schema: Type[T], query_filter: Filter) -> Optional[T]:
        tables = self._schema_tables[schema]
        async with self._engine.begin() as conn:
            records = await _find_records(
                conn, tables, query_filter, limit=1, should_lock=True
            )
            if not records:
                return None
            key_column = tables.table.c[schema.__storage__.key]
            key = getattr(records[0], schema.__storage__.key)
            await conn.execute(delete(tables.table).where(key_column == key))
        return records[0]

    async def delete_many(self, schema: Type[T], query_filter: Filter) -> int:
        tables = self._schema_tables[schema]
        statement = delete(tables.table).where(translate_filter(tables, query_filter))
        async with self._engine.begin() as conn:
            result = await conn.execute(statement)
        return result.rowcount

    async def close(self) -> None:
        if self._expiry_sweeper is not None:
            self._expiry_sweeper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._expiry_sweeper
            self._expiry_sweeper = None
        await self._engine.dispose()

    async def _delete_expired_records(self) -> None:
        """Deletes expired records every expiry_sweep_seconds, as SQL has no TTL index"""
        while True:
            await asyncio.sleep(self._expiry_sweep_seconds)
            now = datetime.now(timezone.utc)
            async with self._engine.begin() as conn:
                for tables in self._schema_tables.values():
                    expires_field = tables.schema.__storage__.expires
                    if expires_field is not None:
                        column = tables.table.c[expires_field]
                        await conn.execute(delete(tables.table).where(column <= now))


async def _find_records(
    conn: AsyncConnection,
    tables: SchemaTables,
    query_filter: Filter,
    sort: Sequence[str] = (),
    skip: int = 0,
    limit: Optional[int] = None,
    should_lock: bool = False,
) -> List[Any]:
    """Finds the matched records, with the elements of their list fields"""
    statement = (
        select(tables.table)
        .where(translate_filter(tables, query_filter))
        .order_by(*translate_sort(tables, sort))
        .offset(skip)
        .limit(limit)
    )
    if should_lock:
        statement = statement.with_for_update()
    rows = [dict(row) for row in (await conn.execute(statement)).mappings()]

    key = tables.schema.__storage__.key
    keys = [row[key] for row in rows]
    for field, list_table in tables.list_tables.items():
        elements_by_key: Dict[Any, List[Any]] = defaultdict(list)
        if keys:
            child = list_table.table
            child_rows = await conn.execute(
                select(child)
                .where(child.c[list_table.parent_column].in_(keys))
                .order_by(child.c[POSITION])
            )
            for child_row in child_rows.mappings():
                elements_by_key[child_row[list_table.parent_column]].append(
                    get_element(list_table, child_row)
                )
        for row in rows:
            row[field] = elements_by_key[row[key]]

    records = []
    for row in rows:
        del row[ROW_ID]
        for name in tables.non_null_fields:
            if name in row and row[name] is None:
                del row[name]
        records.append(tables.schema.model_validate(row))
    return records


async def _get_record(conn: AsyncConnection, tables: SchemaTables, key: Any) -> Any:
    records = await _find_records(conn, tables, {tables.schema.__storage__.key: key})
    return records[0]


async def _find_first_key(
    conn: AsyncConnection, tables: SchemaTables, query_filter: Filter
) -> Any:
    key_column = tables.table.c[tables.schema.__storage__.key]
    statement = (
        select(key_column)
        .where(translate_filter(tables, query_filter))
        .order_by(tables.table.c[ROW_ID])
        .limit(1)
        .with_for_update()
    )
    return await conn.scalar(statement)


async def _insert_record(
    conn: AsyncConnection, tables: SchemaTables, record: Schema
) -> None:
    computed = set(type(record).model_computed_fields)
    values = record.model_dump(exclude=computed or None)
    # as MongoDB gives a document without an _id one
    id_field = tables.schema.model_fields.get("id")
    if values.get("id") is None and is_id_field(id_field):
        values["id"] = generate_id()
    row = {}
    for column in tables.table.columns:
        if column.name == ROW_ID:
            continue
        value = values.get(column.name)
        if column.name in tables.json_fields:
            row[column.name] = to_jsonable_python(value)
        else:
            row[column.name] = convert_to_column_value(value)
    await conn.execute(insert(tables.table).values(**row))

    key = values[tables.schema.__storage__.key]
    for field, list_table in tables.list_tables.items():
        elements = [convert_to_column_value(item) for item in values.get(field) or []]
        if elements:
            await conn.execute(
                insert(list_table.table), get_child_rows(list_table, key, elements)
            )


async def _insert_upserted_record(
    conn: AsyncConnection, tables: SchemaTables, query_filter: Filter, update: Update
) -> Any:
    """Inserts the record an upsert creates, returning its key

    The record starts from the filter's equalities, then takes the update's values. If a
    concurrent write inserted it first, the update is applied to that one instead.
    """
    values: Dict[str, Any] = {}
    for field, condition in query_filter.items():
        if field in LOGICAL_OPERATORS:
            continue
        if not is_operator_map(condition):
            values[field] = condition
        elif "$eq" in condition:
            values[field] = condition["$eq"]
    values.update(update.get("$set", {}))
    values.update(update.get("$setOnInsert", {}))
    values.update(update.get("$inc", {}))
    for field, element in update.get("$addToSet", {}).items():
        values[field] = [element]

    # validated before it is inserted, so it needs the id the insert would give it
    id_field = tables.schema.model_fields.get("id")
    if "id" not in values and is_id_field(id_field):
        values["id"] = generate_id()
    record = tables.schema.model_validate(values)
    try:
        async with conn.begin_nested():
            await _insert_record(conn, tables, record)
    except IntegrityError:
        key = await _find_first_key(conn, tables, query_filter)
        if key is None:
            raise
        await _write_changes(conn, tables, key, translate_update(tables, update))
        return key
    return getattr(record, tables.schema.__storage__.key)


async def _write_changes(
    conn: AsyncConnection, tables: SchemaTables, key: Any, changes: Changes
) -> None:
    """Writes the changes to the record of the key and to its child rows

    Raises:
        QueryError: the changes give the record another key
    """
    key_name = tables.schema.__storage__.key
    if key_name in changes.values and changes.values[key_name] != key:
        raise QueryError(f"an update cannot change {tables.schema.__name__}.{key_name}")
    values = {name: value for name, value in changes.values.items() if name != key_name}
    if values:
        key_column = tables.table.c[key_name]
        await conn.execute(
            update(tables.table).where(key_column == key).values(**values)
        )

    for field, elements in changes.list_replacements.items():
        list_table = tables.list_tables[field]
        child = list_table.table
        parent = child.c[list_table.parent_column]
        await conn.execute(delete(child).where(parent == key))
        if elements:
            await conn.execute(insert(child), get_child_rows(list_table, key, elements))

    for field, element in changes.list_additions:
        list_table = tables.list_tables[field]
        child = list_table.table
        parent = child.c[list_table.parent_column]
        next_position = await conn.scalar(
            select(func.coalesce(func.max(child.c[POSITION]) + 1, 0)).where(
                parent == key
            )
        )
        # a conflict on the (record, element) key means the element is there already
        try:
            async with conn.begin_nested():
                await conn.execute(
                    insert(child).values(
                        **{
                            list_table.parent_column: key,
                            list_table.value_column: element,
                            POSITION: next_position,
                        }
                    )
                )
        except IntegrityError:
            pass

    for field, element in changes.list_removals:
        list_table = tables.list_tables[field]
        child = list_table.table
        await conn.execute(
            delete(child).where(
                child.c[list_table.parent_column] == key,
                child.c[list_table.value_column] == element,
            )
        )


def _set_up_sqlite(sync_engine: Any) -> None:
    """Switches on SQLite's foreign keys, and begins every transaction immediately"""

    @event.listens_for(sync_engine, "connect")
    def on_connect(dbapi_connection: Any, connection_record: Any) -> None:
        # the driver's own transaction handling would begin them lazily
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(sync_engine, "begin")
    def on_begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN IMMEDIATE")


@contextlib.contextmanager
def _translate_unique_violations() -> Iterator[None]:
    """Turns a database's unique violations into the storage layer's DuplicateKeyError"""
    try:
        yield
    except IntegrityError as exp:
        message = str(exp.orig)
        if "UNIQUE constraint failed" in message or "duplicate key value" in message:
            raise DuplicateKeyError(message) from exp
        raise StorageError(message) from exp
