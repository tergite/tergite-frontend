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
"""RedisStore: the DbStore for Redis, adapted from the store the request log used before

Each schema's records are JSON fields of one hash, named after its table and keyed by its
key, and a record expires with its schema's `expires` field through Redis's per-field
expiry. Every other indexed field (the `unique`, `indexes` and `indexed_lists` fields) keeps
a sorted set per value, of the keys of the records holding it, scored by when they expire; a
lookup intersects those sets, and a lookup by key reads the hash. Expired entries are swept from the sets on a write,
at most every `cleanup_interval` seconds.

Filters are what the sets answer: equality or `$in` on indexed fields, joined by `$and`.
Updates `$set` fields, and `$setOnInsert` them when an upsert creates the record. Anything
else raises QueryError: the store serves records found by key or index, such as the request
log, not ad hoc queries. Unique fields other than the key are checked before a write, not
atomically with it.
"""
import enum
import math
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Type, TypeVar

import redis.asyncio
from pydantic import ValidationError

from ..base.exc import DuplicateKeyError, QueryError, StorageError
from ..base.query import Filter, is_operator_map, parse_sort
from ..base.schema import Schema
from ..base.store import DbStore
from ..base.update import Returning, Update

T = TypeVar("T", bound=Schema)
_IDX_SEPARATOR = "::"
_UPDATE_OPERATORS = frozenset({"$set", "$setOnInsert"})


class RedisStore(DbStore):
    """Stores each schema's records in the hash its `__storage__` table names

    The database is the one the URL names, as in `redis://host:6379/0`.
    """

    def __init__(
        self,
        database_url: str,
        schemas: Sequence[Type[Schema]],
        cleanup_interval: float = 3600,
    ):
        self._connection = redis.asyncio.Redis.from_url(
            database_url, decode_responses=True
        )
        self._schemas = tuple(schemas)
        self.__cleanup_interval = cleanup_interval
        self.__last_cleanup_timestamp = time.time()

    async def setup(self) -> None:
        try:
            await self._connection.ping()
        except redis.RedisError as exp:
            raise StorageError(f"Redis is unreachable: {exp}") from exp

    async def get(self, schema: Type[T], key: Any) -> Optional[T]:
        data = await self._connection.hget(
            _get_hashmap_name(schema), _convert_to_text(key)
        )
        return None if data is None else schema.model_validate_json(data)

    async def find(
        self,
        schema: Type[T],
        query_filter: Filter,
        sort: Sequence[str],
        skip: int,
        limit: Optional[int],
    ) -> List[T]:
        records = await self._find_records(schema, query_filter)
        for field, is_descending in reversed(
            parse_sort(sort or (schema.__storage__.key,))
        ):
            records.sort(key=lambda v: _get_sort_key(v, field), reverse=is_descending)
        return _paginate(records, skip=skip, limit=limit)

    async def count(self, schema: Type[T], query_filter: Filter) -> int:
        keys = await self._find_keys(schema, query_filter)
        if keys is None:
            return await self._connection.hlen(_get_hashmap_name(schema))
        return len(await self._find_records(schema, query_filter, keys=keys))

    async def find_distinct(
        self, schema: Type[T], field: str, query_filter: Filter
    ) -> List[Any]:
        distinct: List[Any] = []
        for record in await self._find_records(schema, query_filter):
            value = getattr(record, field)
            for item in value if isinstance(value, list) else [value]:
                if item not in distinct:
                    distinct.append(item)
        return distinct

    async def insert(self, schema: Type[T], record: T) -> T:
        await self._ensure_unique(schema, record)
        key = _get_redis_key(schema, record)
        is_set = await self._connection.hsetnx(
            _get_hashmap_name(schema), key, record.model_dump_json()
        )
        if not is_set:
            raise DuplicateKeyError(f"'{key}' exists in {schema.__storage__.table}")

        pipe = self._connection.pipeline()
        # attempt cleanup of indexes
        await self._cleanup_expired_indexes(pipe, schema)
        # set the record's expiry and insert its indexes
        _set_expiry(pipe, schema, record)
        _insert_indexes(pipe, schema, record)
        await pipe.execute()
        return record

    async def insert_many(self, schema: Type[T], records: Sequence[T]) -> List[T]:
        for record in records:
            await self.insert(schema, record)
        return list(records)

    async def update_one(
        self,
        schema: Type[T],
        query_filter: Filter,
        update: Update,
        should_upsert: bool,
        returning: Returning,
    ) -> Optional[T]:
        _check_update(update)
        records = await self._find_records(schema, query_filter, limit=1)
        if records:
            updated_item = await self._update(schema, records[0], update)
            return records[0] if returning == Returning.BEFORE else updated_item

        if not should_upsert:
            return None
        values = _get_upsert_values(schema, query_filter)
        values.update(update.get("$set", {}))
        values.update(update.get("$setOnInsert", {}))
        created = await self.insert(schema, _validate(schema, values))
        return None if returning == Returning.BEFORE else created

    async def update_many(
        self, schema: Type[T], query_filter: Filter, update: Update
    ) -> int:
        _check_update(update)
        count = 0
        for old_item in await self._find_records(schema, query_filter):
            updated_item = await self._update(schema, old_item, update)
            count += updated_item != old_item
        return count

    async def delete_one(self, schema: Type[T], query_filter: Filter) -> Optional[T]:
        records = await self._find_records(schema, query_filter, limit=1)
        await self._delete(schema, records)
        return records[0] if records else None

    async def delete_many(self, schema: Type[T], query_filter: Filter) -> int:
        records = await self._find_records(schema, query_filter)
        await self._delete(schema, records)
        return len(records)

    async def close(self) -> None:
        await self._connection.aclose()

    async def _find_records(
        self,
        schema: Type[T],
        query_filter: Filter,
        limit: Optional[int] = None,
        keys: Optional[Set[str]] = None,
    ) -> List[T]:
        """Gets the records the filter matches, in the order of their keys"""
        hashmap_name = _get_hashmap_name(schema)
        if keys is None:
            keys = await self._find_keys(schema, query_filter)
        if keys is None:
            raw_data = list((await self._connection.hgetall(hashmap_name)).values())
        else:
            matched_keys = _paginate(sorted(keys), limit=limit)
            if len(matched_keys) == 0:
                return []
            raw_data = await self._connection.hmget(hashmap_name, matched_keys)

        records = [schema.model_validate_json(item) for item in raw_data if item]
        records.sort(key=lambda v: _get_redis_key(schema, v))
        return _paginate(records, limit=limit)

    async def _find_keys(
        self, schema: Type[Schema], query_filter: Filter
    ) -> Optional[Set[str]]:
        """Gets the keys of the records the filter matches; None when it matches all

        Raises:
            QueryError: the filter needs more than the indexes can answer
        """
        conditions = _get_index_conditions(schema, query_filter)
        if len(conditions) == 0:
            return None

        current_timestamp = time.time()
        matched_keys: Optional[Set[str]] = None
        for field, values in conditions:
            keys: Set[str] = set()
            if field == schema.__storage__.key:
                # the key names the record's field in the hash, which a read checks
                keys.update(_convert_to_text(value) for value in values)
                values = ()
            for value in values:
                idx_key = _get_index_key(schema, field, value)
                keys.update(
                    await self._connection.zrangebyscore(
                        idx_key, current_timestamp, "+inf"
                    )
                )
            matched_keys = keys if matched_keys is None else matched_keys & keys
            if not matched_keys:
                break
        return matched_keys

    async def _ensure_unique(
        self, schema: Type[Schema], record: Schema, own_key: Optional[str] = None
    ) -> None:
        """Checks that no other record holds the record's unique values

        Raises:
            DuplicateKeyError: another record holds them
        """
        for fields in _get_unique_groups(schema):
            group_filter = {field: _get_value(record, field) for field in fields}
            keys = await self._find_keys(schema, group_filter) or set()
            if keys - {own_key}:
                raise DuplicateKeyError(
                    f"{schema.__storage__.table}: {group_filter} is taken"
                )

    async def _update(self, schema: Type[T], old_item: T, update: Update) -> T:
        """Writes the record with the update's $set applied, returning it"""
        new_props = old_item.model_dump()
        for field, value in update.get("$set", {}).items():
            _set_path(new_props, field, value)
        updated_item = _validate(schema, new_props)

        key = _get_redis_key(schema, old_item)
        if _get_redis_key(schema, updated_item) != key:
            raise QueryError(f"an update cannot change {schema.__storage__.key}")
        await self._ensure_unique(schema, updated_item, own_key=key)

        pipe = self._connection.pipeline()
        # attempt cleanup of indexes
        await self._cleanup_expired_indexes(pipe, schema)
        # update record and indexes
        pipe.hset(_get_hashmap_name(schema), key, updated_item.model_dump_json())
        _set_expiry(pipe, schema, updated_item)
        _delete_indexes(pipe, schema, [old_item])
        _insert_indexes(pipe, schema, updated_item)
        await pipe.execute()
        return updated_item

    async def _delete(self, schema: Type[Schema], records: List[Schema]) -> None:
        """Deletes the records and their index entries"""
        redis_keys = [_get_redis_key(schema, item) for item in records]
        pipe = self._connection.pipeline()
        if len(redis_keys) > 0:
            pipe.hdel(_get_hashmap_name(schema), *redis_keys)

        # attempt cleanup of indexes
        await self._cleanup_expired_indexes(pipe, schema)

        # delete the index entries for the deleted items
        _delete_indexes(pipe, schema, records)
        await pipe.execute()

    async def _get_all_index_keys(self, schema: Type[Schema]) -> List[str]:
        """Gets all the index keys of the schema"""
        index_pattern = f"{_get_index_prefix(schema)}{_IDX_SEPARATOR}*"
        return [
            idx_key
            async for idx_key in self._connection.scan_iter(
                match=index_pattern, _type="ZSET"
            )
        ]

    async def _cleanup_expired_indexes(self, pipe: Any, schema: Type[Schema]) -> None:
        """Queues the removal of expired index entries, at most every cleanup_interval"""
        current_timestamp = time.time()
        elapsed_time = current_timestamp - self.__last_cleanup_timestamp

        if elapsed_time > self.__cleanup_interval:
            for idx_key in await self._get_all_index_keys(schema):
                pipe.zremrangebyscore(idx_key, 0, current_timestamp)

            self.__last_cleanup_timestamp = current_timestamp


def _check_update(update: Update) -> None:
    unsupported = set(update) - _UPDATE_OPERATORS
    if unsupported:
        raise QueryError(f"RedisStore does not support the updates {unsupported}")


def _get_index_conditions(
    schema: Type[Schema], query_filter: Filter
) -> List[Tuple[str, List[Any]]]:
    """Gets (field, values) pairs, each matching a record holding any of the values

    Raises:
        QueryError: a condition other than equality or $in, or on a field not indexed
    """
    conditions = []
    for field, condition in query_filter.items():
        if field == "$and":
            for item in condition:
                conditions.extend(_get_index_conditions(schema, item))
            continue
        if field.startswith("$"):
            raise QueryError(f"RedisStore does not support '{field}'")
        if field != schema.__storage__.key and field not in _get_index_fields(schema):
            raise QueryError(f"the field '{field}' is not indexed")

        if not is_operator_map(condition):
            conditions.append((field, [condition]))
        elif set(condition) == {"$eq"}:
            conditions.append((field, [condition["$eq"]]))
        elif set(condition) == {"$in"}:
            conditions.append((field, list(condition["$in"])))
        else:
            raise QueryError(f"RedisStore supports only equality and $in on '{field}'")
    return conditions


def _get_upsert_values(schema: Type[Schema], query_filter: Filter) -> Dict[str, Any]:
    """Gets the values an upsert starts a record with: the filter's single values"""
    return {
        field: values[0]
        for field, values in _get_index_conditions(schema, query_filter)
        if len(values) == 1
    }


def _get_index_fields(schema: Type[Schema]) -> Tuple[str, ...]:
    """The fields kept in sorted sets: the unique, indexed and list fields but the key"""
    spec = schema.__storage__
    index_map = {}
    for group in (*spec.unique, *spec.indexes):
        for field in (group,) if isinstance(group, str) else group:
            index_map[field.lstrip("-")] = None
    index_map.update({field: None for field in spec.indexed_lists})
    index_map.pop(spec.key, None)
    return tuple(index_map)


def _get_unique_groups(schema: Type[Schema]) -> List[Tuple[str, ...]]:
    """The unique fields, alone or in groups, other than the key, which is unique anyway"""
    spec = schema.__storage__
    groups = [
        (group,) if isinstance(group, str) else tuple(group) for group in spec.unique
    ]
    return [fields for fields in groups if spec.key not in fields]


def _insert_indexes(pipe: Any, schema: Type[Schema], record: Schema) -> None:
    """Queues the index entries of the record, scored by when it expires"""
    record_key = _get_redis_key(schema, record)
    expiry_timestamp = _get_expiry_timestamp(schema, record)
    for idx_key in _get_index_keys(schema, record):
        pipe.zadd(idx_key, {record_key: expiry_timestamp})


def _delete_indexes(pipe: Any, schema: Type[Schema], records: List[Schema]) -> None:
    """Queues the removal of the index entries of the records"""
    for item in records:
        key = _get_redis_key(schema, item)
        for idx_key in _get_index_keys(schema, item):
            pipe.zrem(idx_key, key)


def _set_expiry(pipe: Any, schema: Type[Schema], record: Schema) -> None:
    """Queues the record's expiry, or its removal if it has none"""
    hashmap_name = _get_hashmap_name(schema)
    key = _get_redis_key(schema, record)
    expiry_timestamp = _get_expiry_timestamp(schema, record)
    if math.isinf(expiry_timestamp):
        pipe.hpersist(hashmap_name, key)
    else:
        pipe.hpexpireat(hashmap_name, int(expiry_timestamp * 1000), key)


def _get_expiry_timestamp(schema: Type[Schema], record: Schema) -> float:
    """Gets when the record expires, as a unix timestamp; by default, items last forever"""
    expires_field = schema.__storage__.expires
    expires_at = None if expires_field is None else getattr(record, expires_field)
    return math.inf if expires_at is None else expires_at.timestamp()


def _get_index_keys(schema: Type[Schema], item: Schema) -> List[str]:
    """Gets the keys of the sorted sets indexing the item, one per value of each field"""
    index_keys = []
    for field in _get_index_fields(schema):
        value = _get_value(item, field)
        for member in value if isinstance(value, list) else [value]:
            index_keys.append(_get_index_key(schema, field, member))
    return index_keys


def _get_index_key(schema: Type[Schema], field: str, value: Any) -> str:
    text = _convert_to_text(value)
    if field in schema.__storage__.case_insensitive:
        text = text.casefold()
    return f"{_get_index_prefix(schema)}{_IDX_SEPARATOR}{field}{_IDX_SEPARATOR}{text}"


def _get_index_prefix(schema: Type[Schema]) -> str:
    return f"__index__{_get_hashmap_name(schema)}_"


def _get_hashmap_name(schema: Type[Schema]) -> str:
    return schema.__storage__.table


def _get_redis_key(schema: Type[Schema], item: Schema) -> str:
    """Gets the redis key of the item: its key field's value"""
    return _convert_to_text(getattr(item, schema.__storage__.key))


def _get_value(item: Schema, field: str) -> Any:
    """Gets the value at a dotted path of the item, or None if it is missing"""
    value: Any = item
    for part in field.split("."):
        value = (
            value.get(part) if isinstance(value, dict) else getattr(value, part, None)
        )
    return value


def _get_sort_key(item: Schema, field: str) -> tuple:
    value = _get_value(item, field)
    return (0,) if value is None else (1, value)


def _set_path(values: Dict[str, Any], field: str, value: Any) -> None:
    *parents, name = field.split(".")
    target = values
    for part in parents:
        target = target.setdefault(part, {})
    target[name] = value


def _convert_to_text(value: Any) -> str:
    return str(value.value if isinstance(value, enum.Enum) else value)


def _validate(schema: Type[T], values: Dict[str, Any]) -> T:
    try:
        return schema.model_validate(values)
    except ValidationError as exp:
        raise QueryError(f"the values leave {schema.__name__} invalid: {exp}") from exp


def _paginate(data: List[Any], skip: int = 0, limit: Optional[int] = None) -> List[Any]:
    """Paginates the data basing on the skip and the limit params"""
    slice_limit = limit
    if isinstance(slice_limit, int):
        slice_limit += skip
    return data[skip:slice_limit]
