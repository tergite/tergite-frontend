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
"""Tests of RedisStore, adapted from those of the store the request log used before

Keys are one field in the Database, so the old tests of tuple and dict keys collapse into
those of single keys, and a record's ttl is its `expires_at` field.
"""
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pytest
import redis
from pydantic import Field

from libs.storage import (
    Database,
    DuplicateKeyError,
    QueryError,
    Returning,
    Schema,
    StorageSpec,
)
from libs.storage.redis import RedisStore
from tests._utils.env import TEST_REDIS_URL

# the app's tests use the URL's own database; these take another, as they flush it
_DATABASE_URL = urlunsplit(urlsplit(TEST_REDIS_URL)._replace(path="/15"))


class _Status(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    FAILED = "failed"
    SUCCESSFUL = "successful"


class AuthLog(Schema):
    __storage__ = StorageSpec(
        table="auth_logs",
        key="job_id",
        indexes=("app_token", "status"),
        expires="expires_at",
    )

    job_id: str
    app_token: str
    status: _Status = _Status.PENDING
    created_at: str = Field(default_factory=lambda: _get_current_timestamp())
    expires_at: Optional[datetime] = None


class Owner(Schema):
    __storage__ = StorageSpec(
        table="owners", key="id", unique=("email",), case_insensitive=("email",)
    )

    id: str
    email: str


_AUTH_LOG_LIST = [
    {"job_id": "foo", "app_token": "bar"},
    {"job_id": "foot", "app_token": "bar", "status": "executing"},
    {"job_id": "feet", "app_token": "ben", "status": "failed"},
    {"job_id": "fee", "app_token": "barracuda"},
    {"job_id": "billings", "app_token": "zealot"},
]
# a pending and an executing log; the multi-record tests use the whole list
_SAMPLE_AUTH_LOGS = _AUTH_LOG_LIST[:2]
_DELETE_SLICES = [
    (0, -1),
    (1, 4),
    (2, 3),
]

# the key, job_id, has no index: a lookup by key reads the hash
_INDEX_PREFIXES = {
    "app_token": "__index__auth_logs_::app_token::",
    "status": "__index__auth_logs_::status::",
}


@pytest.fixture(autouse=True)
def redis_client():
    client = redis.Redis.from_url(_DATABASE_URL, decode_responses=True)
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def make_database(mocker):
    """Makes a Database on a RedisStore that sweeps expired indexes as often as asked"""

    def make(cleanup_interval: float = 3600) -> Database:
        store = RedisStore(
            _DATABASE_URL, schemas=[AuthLog, Owner], cleanup_interval=cleanup_interval
        )
        mocker.patch("libs.storage.database._create_store", return_value=store)
        return Database(_DATABASE_URL, schemas=[AuthLog, Owner])

    yield make


@pytest.fixture
async def auth_logs(make_database):
    database = make_database()
    yield database
    await database.close()


@pytest.mark.parametrize("payload", _SAMPLE_AUTH_LOGS)
async def test_update_one_sets_fields(redis_client, auth_logs, payload):
    """Calling update_one() updates the item if it exists already"""
    original_item = AuthLog(**{**payload, "status": "pending"})
    _insert_into_redis(redis_client, [original_item])
    original_item_in_db = _get_redis_value(redis_client, original_item)

    new_item = await auth_logs.update_one(
        AuthLog, {"job_id": payload["job_id"]}, {"$set": {"status": "successful"}}
    )
    new_item_in_db = _get_redis_value(redis_client, original_item)

    assert original_item_in_db == original_item.model_dump_json()
    assert new_item_in_db == new_item.model_dump_json()
    assert new_item.model_dump() == {
        **original_item.model_dump(),
        "status": _Status.SUCCESSFUL,
    }


@pytest.mark.parametrize("payload", _AUTH_LOG_LIST[:1])
async def test_update_one_with_an_expiry_expires_the_item(
    redis_client, make_database, payload
):
    """Calling update_one() with expires_at updates the item and when it expires"""
    auth_logs = make_database(cleanup_interval=1)
    original_item = AuthLog(**{**payload, "status": "pending"})
    await auth_logs.insert(AuthLog, original_item)

    ttl = 1
    new_item = await auth_logs.update_one(
        AuthLog,
        {"job_id": payload["job_id"]},
        {"$set": {"status": "successful", "expires_at": _get_relative_time(ttl)}},
    )
    new_item_in_db = _get_redis_value(redis_client, original_item)

    time.sleep(ttl * 1.5)

    assert await auth_logs.get(AuthLog, payload["job_id"]) is None

    # a mutation to force cleanup
    await auth_logs.delete_many(AuthLog, {"job_id": "non-existent"})

    assert new_item_in_db == new_item.model_dump_json()
    assert _get_redis_value(redis_client, original_item) is None
    for idx_key in _get_redis_index_keys(new_item):
        assert redis_client.zrange(idx_key, 0, -1) == []
    await auth_logs.close()


@pytest.mark.parametrize("payload", _AUTH_LOG_LIST[:1])
async def test_update_one_keeps_the_expiry_it_does_not_change(
    redis_client, auth_logs, payload
):
    """Calling update_one() leaves the item expiring when it did"""
    ttl = 0.5
    original_item = AuthLog(**payload, expires_at=_get_relative_time(ttl))
    await auth_logs.insert(AuthLog, original_item)

    await auth_logs.update_one(
        AuthLog, {"job_id": payload["job_id"]}, {"$set": {"status": "successful"}}
    )

    time.sleep(ttl)

    assert await auth_logs.get(AuthLog, payload["job_id"]) is None


@pytest.mark.parametrize("payload", _AUTH_LOG_LIST[:1])
async def test_update_one_persists_or_expires_the_item_as_asked(
    redis_client, auth_logs, payload
):
    """Calling update_one() with expires_at None persists the item; with a time, expires it"""
    ttl = 0.5
    job_filter = {"job_id": payload["job_id"]}
    await auth_logs.insert(
        AuthLog, AuthLog(**payload, expires_at=_get_relative_time(ttl))
    )

    new_item = await auth_logs.update_one(
        AuthLog, job_filter, {"$set": {"expires_at": None}}
    )

    time.sleep(ttl)
    assert await auth_logs.get(AuthLog, payload["job_id"]) == new_item

    custom_ttl = 0.3
    await auth_logs.update_one(
        AuthLog, job_filter, {"$set": {"expires_at": _get_relative_time(custom_ttl)}}
    )

    time.sleep(custom_ttl)

    assert await auth_logs.get(AuthLog, payload["job_id"]) is None


@pytest.mark.parametrize("payload", _SAMPLE_AUTH_LOGS)
async def test_update_not_found(redis_client, auth_logs, payload):
    """Calling update_one() and update_many() changes nothing if the item does not exist"""
    job_filter = {"job_id": payload["job_id"]}
    update = {"$set": {"status": "successful"}}

    assert await auth_logs.update_one(AuthLog, job_filter, update) is None
    assert await auth_logs.update_many(AuthLog, job_filter, update) == 0
    assert _get_redis_hmap(redis_client) == {}


@pytest.mark.parametrize("payload", _SAMPLE_AUTH_LOGS)
async def test_update_invalid_model(redis_client, auth_logs, payload):
    """update_one() fails if the update leaves the item off the model"""
    original_item = AuthLog(**{**payload, "status": "pending"})
    _insert_into_redis(redis_client, [original_item])
    original_item_in_db = _get_redis_value(redis_client, original_item)

    with pytest.raises(QueryError, match=r"AuthLog invalid"):
        await auth_logs.update_one(
            AuthLog, {"job_id": payload["job_id"]}, {"$set": {"status": 9}}
        )

    assert _get_redis_value(redis_client, original_item) == original_item_in_db


@pytest.mark.parametrize("payload", _SAMPLE_AUTH_LOGS)
async def test_update_indexes(redis_client, auth_logs, payload):
    """Calling update_one() updates the redis index keys"""
    first_item = AuthLog(**{**payload, "status": "pending"})
    second_item = AuthLog(**{**payload, "status": "pending", "job_id": f"{uuid4()}"})

    await auth_logs.insert(AuthLog, first_item)
    await auth_logs.insert(AuthLog, second_item)
    first_redis_key = _get_redis_key(first_item)
    second_redis_key = _get_redis_key(second_item)

    new_first_item = await auth_logs.update_one(
        AuthLog,
        {"job_id": first_item.job_id},
        {"$set": {"status": "successful", "app_token": f"{payload['app_token']}-new"}},
    )

    status_idx_prefix = _INDEX_PREFIXES["status"]
    app_token_idx_prefix = _INDEX_PREFIXES["app_token"]

    # status changed
    new_first_status_idx_key = f"{status_idx_prefix}{new_first_item.status.value}"
    second_status_idx_key = f"{status_idx_prefix}{second_item.status.value}"

    assert redis_client.zrange(new_first_status_idx_key, 0, -1) == [first_redis_key]
    assert redis_client.zrange(second_status_idx_key, 0, -1) == [second_redis_key]

    # app_token changed for the first only
    new_app_token_idx_key = f"{app_token_idx_prefix}{new_first_item.app_token}"
    old_app_token_idx_key = f"{app_token_idx_prefix}{first_item.app_token}"

    assert redis_client.zrange(new_app_token_idx_key, 0, -1) == [first_redis_key]
    assert redis_client.zrange(old_app_token_idx_key, 0, -1) == [second_redis_key]


async def test_update_cannot_change_the_key(auth_logs):
    await auth_logs.insert(AuthLog, AuthLog(**_AUTH_LOG_LIST[0]))

    with pytest.raises(QueryError):
        await auth_logs.update_one(
            AuthLog, {"job_id": "foo"}, {"$set": {"job_id": "other"}}
        )


async def test_update_one_upserts(auth_logs):
    created = await auth_logs.update_one(
        AuthLog,
        {"job_id": "new", "app_token": "bar"},
        {"$set": {"status": "executing"}, "$setOnInsert": {"created_at": "x"}},
        should_upsert=True,
        returning=Returning.AFTER,
    )

    assert created == AuthLog(
        job_id="new", app_token="bar", status="executing", created_at="x"
    )
    assert await auth_logs.get(AuthLog, "new") == created


@pytest.mark.parametrize("payload", _AUTH_LOG_LIST[:1])
async def test_insert(redis_client, make_database, payload):
    """Calling insert() stores the item, expiring it when its expires_at says"""
    auth_logs = make_database(cleanup_interval=0.3)
    ttl = 0.5
    persistent_item = AuthLog(**{**payload, "status": "pending"})
    expiring_item = AuthLog(
        **{**payload, "job_id": f"per{payload['job_id']}"},
        expires_at=_get_relative_time(ttl),
    )

    await auth_logs.insert(AuthLog, persistent_item)
    await auth_logs.insert(AuthLog, expiring_item)
    expiring_item_in_db = _get_redis_value(redis_client, expiring_item)

    time.sleep(ttl)

    persistent_item_from_api = await auth_logs.get(AuthLog, persistent_item.job_id)
    expiring_item_from_api = await auth_logs.get(AuthLog, expiring_item.job_id)

    # do a mutation like delete_many to force cleanup of raw db stuff
    await auth_logs.delete_many(AuthLog, {"job_id": "non-existent"})

    assert expiring_item_in_db == expiring_item.model_dump_json()
    assert persistent_item_from_api == persistent_item
    assert expiring_item_from_api is None
    assert _get_redis_value(redis_client, persistent_item) == (
        persistent_item.model_dump_json()
    )
    assert _get_redis_value(redis_client, expiring_item) is None
    await auth_logs.close()


@pytest.mark.parametrize("payload", _SAMPLE_AUTH_LOGS)
async def test_insert_refuses_an_existing_key(redis_client, auth_logs, payload):
    """Calling insert() on an existing key fails, leaving the item as it was"""
    item = AuthLog(**{**payload, "status": "pending"})
    await auth_logs.insert(AuthLog, item)

    with pytest.raises(DuplicateKeyError):
        await auth_logs.insert(
            AuthLog, item.model_copy(update={"status": _Status.FAILED})
        )

    assert _get_redis_value(redis_client, item) == item.model_dump_json()


async def test_insert_index(redis_client, make_database):
    """Calling insert() inserts some indexes"""
    auth_logs = make_database(cleanup_interval=0.1)
    item_ttl_pairs = [
        (AuthLog(**payload), None if i % 2 else 0.2)
        for i, payload in enumerate(_AUTH_LOG_LIST)
    ]

    expected_indexes: Dict[str, List[str]] = {}
    persistent_indexes: Dict[str, List[str]] = {}
    for item, ttl in item_ttl_pairs:
        if ttl is not None:
            item.expires_at = _get_relative_time(ttl)
        await auth_logs.insert(AuthLog, item)
        redis_item_key = _get_redis_key(item)
        for idx_key in _get_redis_index_keys(item):
            expected_indexes.setdefault(idx_key, []).append(redis_item_key)
            if ttl is None:
                persistent_indexes.setdefault(idx_key, []).append(redis_item_key)

    for idx_key, expected in expected_indexes.items():
        got = redis_client.zrange(idx_key, 0, -1)
        assert sorted(got) == sorted(expected)

    time.sleep(0.2)

    # do a mutation like delete_many to force cleanup of indexes
    await auth_logs.delete_many(AuthLog, {"job_id": "non-existent"})

    for idx_key in expected_indexes:
        got = redis_client.zrange(idx_key, 0, -1)
        assert sorted(got) == sorted(persistent_indexes.get(idx_key, []))
    await auth_logs.close()


async def test_insert_invalid_model(redis_client, auth_logs):
    """insert() fails if the item is not of the schema"""
    with pytest.raises(TypeError):
        await auth_logs.insert(AuthLog, Owner(id="foo", email="a@example.com"))

    assert _get_redis_hmap(redis_client) == {}


async def test_unique_fields_refuse_duplicates(auth_logs):
    await auth_logs.insert(Owner, Owner(id="1", email="ann@example.com"))
    bob = await auth_logs.insert(Owner, Owner(id="2", email="bob@example.com"))

    with pytest.raises(DuplicateKeyError):
        await auth_logs.insert(Owner, Owner(id="3", email="ANN@example.com"))
    with pytest.raises(DuplicateKeyError):
        await auth_logs.update_one(
            Owner, {"id": bob.id}, {"$set": {"email": "Ann@example.com"}}
        )
    assert await auth_logs.count(Owner, {"email": "ANN@EXAMPLE.COM"}) == 1


@pytest.mark.parametrize("payload", _SAMPLE_AUTH_LOGS)
async def test_get(redis_client, auth_logs, payload):
    """Calling get() gets the item identified by the given key"""
    item = AuthLog(**{**payload, "status": "pending"})
    _insert_into_redis(redis_client, [item])

    assert _get_redis_value(redis_client, item) == item.model_dump_json()
    assert await auth_logs.get(AuthLog, payload["job_id"]) == item


@pytest.mark.parametrize("payload", _SAMPLE_AUTH_LOGS)
async def test_get_not_found(auth_logs, payload):
    """Calling get() returns None if item is nonexistent"""
    assert await auth_logs.get(AuthLog, payload["job_id"]) is None


@pytest.mark.parametrize("desc", [True, False])
async def test_find_all(redis_client, auth_logs, desc):
    """Calling find() with no filter gets the items in the collection sorted"""
    items = [AuthLog(**payload) for payload in _AUTH_LOG_LIST]
    sorted_items = _sort_by_key(items, desc=desc)
    _insert_into_redis(redis_client, items)

    got = await auth_logs.find(AuthLog, sort=["-job_id" if desc else "job_id"])
    expected_hmap = {_get_redis_key(v): v.model_dump_json() for v in sorted_items}

    assert got == sorted_items
    assert _get_redis_hmap(redis_client) == expected_hmap


async def test_find_by_keys(auth_logs):
    """Calling find() with $in on the key gets the items with the given keys"""
    items = [AuthLog(**payload) for payload in _AUTH_LOG_LIST]
    for item in items:
        await auth_logs.insert(AuthLog, item)
    keys = [v.job_id for v in items]

    def find_by_keys(*job_ids: str):
        return auth_logs.find(AuthLog, {"job_id": {"$in": list(job_ids)}})

    assert await find_by_keys(*keys[1:], "non-existent") == _sort_by_key(items[1:])
    assert await find_by_keys(*keys) == _sort_by_key(items)
    assert await find_by_keys(*keys[:-1], "some-random") == _sort_by_key(items[:-1])


async def test_find_by_index(auth_logs):
    """Calling find() gets the items by searching in its indexes"""
    items = [AuthLog(**payload) for payload in _AUTH_LOG_LIST]
    for item in items:
        await auth_logs.insert(AuthLog, item)

    def sort(data: List[AuthLog]) -> List[AuthLog]:
        """Sorts by job_id"""
        return sorted(data, key=lambda v: v.job_id)

    pending = _Status.PENDING
    executing = _Status.EXECUTING
    failed = _Status.FAILED

    def find(**fields) -> List[AuthLog]:
        return [v for v in items if all(getattr(v, k) == x for k, x in fields.items())]

    assert await auth_logs.find(AuthLog, {"status": pending}) == sort(
        find(status=pending)
    )
    assert await auth_logs.find(AuthLog, {"status": executing}) == sort(
        find(status=executing)
    )
    assert await auth_logs.find(AuthLog, {"status": failed}) == sort(
        find(status=failed)
    )
    assert await auth_logs.find(AuthLog, {"job_id": "feet"}) == find(job_id="feet")
    assert await auth_logs.find(AuthLog, {"app_token": "bar"}) == sort(
        find(app_token="bar")
    )
    assert await auth_logs.find(
        AuthLog, {"app_token": "bar", "status": pending}
    ) == sort(find(app_token="bar", status=pending))
    assert await auth_logs.find(
        AuthLog, {"$and": [{"app_token": "bar"}, {"status": {"$in": [executing]}}]}
    ) == sort(find(app_token="bar", status=executing))
    assert await auth_logs.count(AuthLog, {"app_token": "bar"}) == 2
    assert await auth_logs.find_distinct(AuthLog, "app_token", {"status": pending}) == [
        "zealot",
        "barracuda",
        "bar",
    ]


@pytest.mark.parametrize(
    "query_filter",
    [
        {"created_at": "x"},
        {"status": {"$ne": "pending"}},
        {"$or": [{"status": "pending"}]},
    ],
)
async def test_find_refuses_what_the_indexes_cannot_answer(auth_logs, query_filter):
    with pytest.raises(QueryError):
        await auth_logs.find(AuthLog, query_filter)


async def test_unsupported_updates_are_refused(auth_logs):
    with pytest.raises(QueryError):
        await auth_logs.update_many(AuthLog, {}, {"$inc": {"status": 1}})


@pytest.mark.parametrize("bounds", _DELETE_SLICES)
async def test_delete_many_by_keys(redis_client, auth_logs, bounds: Tuple[int, int]):
    """Calling delete_many() removes items with matching keys in the collection"""
    items = [AuthLog(**payload) for payload in _AUTH_LOG_LIST]
    keys_to_delete = [item.job_id for item in items[bounds[0] : bounds[1]]]
    expected_items = items[: bounds[0]] + items[bounds[1] :]

    _insert_into_redis(redis_client, items)

    count = await auth_logs.delete_many(AuthLog, {"job_id": {"$in": keys_to_delete}})
    expected_hmap = {_get_redis_key(v): v.model_dump_json() for v in expected_items}

    assert count == len(keys_to_delete)
    assert _get_redis_hmap(redis_client) == expected_hmap


@pytest.mark.parametrize("payload", _SAMPLE_AUTH_LOGS)
async def test_delete_indexes(redis_client, auth_logs, payload):
    """Calling delete_one() updates the redis index keys"""
    first_item = AuthLog(**{**payload, "status": "successful"})
    second_item = AuthLog(**{**payload, "status": "pending", "job_id": f"{uuid4()}"})

    await auth_logs.insert(AuthLog, first_item)
    await auth_logs.insert(AuthLog, second_item)
    second_redis_key = _get_redis_key(second_item)

    deleted = await auth_logs.delete_one(AuthLog, {"job_id": first_item.job_id})

    status_idx_prefix = _INDEX_PREFIXES["status"]
    app_token_idx_prefix = _INDEX_PREFIXES["app_token"]

    first_status_idx_key = f"{status_idx_prefix}{first_item.status.value}"
    second_status_idx_key = f"{status_idx_prefix}{second_item.status.value}"
    # app_token was same in both
    app_token_idx_key = f"{app_token_idx_prefix}{first_item.app_token}"

    assert deleted == first_item
    assert redis_client.zrange(first_status_idx_key, 0, -1) == []
    assert redis_client.zrange(second_status_idx_key, 0, -1) == [second_redis_key]
    assert redis_client.zrange(app_token_idx_key, 0, -1) == [second_redis_key]


async def test_clear(redis_client, auth_logs):
    """Calling delete_many() with an empty filter removes all items in the hashmap"""
    items = [AuthLog(**payload) for payload in _AUTH_LOG_LIST]
    _insert_into_redis(redis_client, items)

    assert await auth_logs.delete_many(AuthLog, {}) == len(items)
    assert _get_redis_hmap(redis_client) == {}


@pytest.mark.parametrize("payload", _SAMPLE_AUTH_LOGS)
async def test_clear_indexes(redis_client, auth_logs, payload):
    """Calling delete_many() with an empty filter removes all the redis index keys"""
    first_item = AuthLog(**{**payload, "status": "successful"})
    second_item = AuthLog(**{**payload, "status": "pending", "job_id": f"{uuid4()}"})

    await auth_logs.insert(AuthLog, first_item)
    await auth_logs.insert(AuthLog, second_item)

    await auth_logs.delete_many(AuthLog, {})

    for idx_key in [
        *_get_redis_index_keys(first_item),
        *_get_redis_index_keys(second_item),
    ]:
        assert redis_client.zrange(idx_key, 0, -1) == []


def _get_current_timestamp() -> str:
    """Gets the current timestamp"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_relative_time(seconds: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def _get_redis_value(client: redis.Redis, item: AuthLog) -> Optional[str]:
    """Gets the value of the item in redis, or None if it does not exist"""
    return client.hget("auth_logs", _get_redis_key(item))


def _get_redis_hmap(client: redis.Redis) -> Dict[str, str]:
    """Gets the full hashmap of the auth logs in redis"""
    return client.hgetall("auth_logs")


def _insert_into_redis(client: redis.Redis, items: List[AuthLog]) -> None:
    """Inserts the items into redis around the store, without indexes"""
    if items:
        client.hset(
            "auth_logs",
            mapping={_get_redis_key(item): item.model_dump_json() for item in items},
        )


def _get_redis_key(item: AuthLog) -> str:
    return item.job_id


def _get_redis_index_keys(item: AuthLog) -> List[str]:
    """Gets the keys of the indexes of the item in redis"""
    return [
        f"{prefix}{getattr(getattr(item, prop), 'value', getattr(item, prop))}"
        for prop, prefix in _INDEX_PREFIXES.items()
    ]


def _sort_by_key(items: List[AuthLog], desc: bool = False) -> List[AuthLog]:
    return sorted(items, key=_get_redis_key, reverse=desc)
