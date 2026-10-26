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

from typing import Any, Dict, List, Optional

import pytest
from pydantic import BaseModel, ConfigDict, Field

from libs.storage import (
    Database,
    Id,
    QueryError,
    Schema,
    StorageError,
    StorageSpec,
    StorageSpecError,
    UnknownFieldError,
    UnknownSchemaError,
    generate_id,
)
from libs.storage.base.query import parse_sort
from libs.storage.base.store import DbStore


class _Owner(Schema):
    __storage__ = StorageSpec(table="owners")

    id: Id = Field(default_factory=generate_id)


class _Timestamps(BaseModel):
    started: Optional[str] = None


class _Pet(Schema):
    __storage__ = StorageSpec(
        table="pets",
        unique=("name",),
        references={"owner_id": _Owner},
        indexed_lists=("tags",),
        indexes=(("owner_id", "-created_at"),),
    )

    id: Id = Field(default_factory=generate_id)
    name: str
    owner_id: Optional[Id] = None
    tags: List[str] = []
    timestamps: _Timestamps = _Timestamps()
    extra: Dict[str, Any] = {}
    created_at: str = ""


@pytest.fixture
def store(mocker):
    store = _RecordingStore()
    mocker.patch("libs.storage.database._create_store", return_value=store)
    yield store


@pytest.fixture
def database(store):
    yield Database("memory://", schemas=[_Owner, _Pet])


async def test_calls_reach_the_store(database, store):
    pet_filter = {"name": "Rex", "timestamps.started": None}
    update = {"$set": {"extra.colour": "red"}}

    await database.find(_Pet, filter=pet_filter, sort=["-name"], skip=1)
    await database.update_many(_Pet, filter={}, update=update)

    assert store.calls == [
        (
            "find",
            _Pet,
            {"filter": pet_filter, "sort": ["-name"], "skip": 1, "limit": None},
        ),
        ("update_many", _Pet, {"filter": {}, "update": update}),
    ]


async def test_find_one_asks_for_one_record(database, store):
    store.found = [_Pet(name="Rex")]

    got = await database.find_one(_Pet, filter={"name": "Rex"})

    assert got is store.found[0]
    assert store.calls[0][2]["limit"] == 1


@pytest.mark.parametrize(
    "call",
    [
        lambda db: db.get(_Stray, generate_id()),
        lambda db: db.find(_Stray),
        lambda db: db.count(_Stray),
        lambda db: db.delete_many(_Stray, filter={}),
    ],
)
async def test_a_schema_the_database_was_not_given_is_refused(database, call):
    with pytest.raises(UnknownSchemaError):
        await call(database)


@pytest.mark.parametrize(
    "call",
    [
        lambda db: db.find(_Pet, filter={"nmae": "Rex"}),
        lambda db: db.find(_Pet, filter={"$or": [{"name": "a"}, {"nmae": "b"}]}),
        lambda db: db.find(_Pet, sort=["-timestamps.ended"]),
        lambda db: db.update_many(_Pet, filter={}, update={"$set": {"tag": "x"}}),
        lambda db: db.find_distinct(_Pet, "owner"),
    ],
)
async def test_a_field_the_schema_does_not_have_is_refused(database, store, call):
    with pytest.raises(UnknownFieldError):
        await call(database)

    assert store.calls == []


@pytest.mark.parametrize(
    "call",
    [
        lambda db: db.find(_Pet, filter={"name": {"$regex": "R"}}),
        lambda db: db.find(_Pet, filter={"$where": "1"}),
        lambda db: db.find(_Pet, filter={"name": {"$in": "Rex"}}),
        lambda db: db.find(_Pet, filter={"$or": []}),
        lambda db: db.update_many(_Pet, filter={}, update={"$rename": {"name": "x"}}),
        lambda db: db.update_many(_Pet, filter={}, update={"$set": {}}),
        lambda db: db.update_many(_Pet, filter={}, update={"$inc": {"name": "1"}}),
        lambda db: db.update_many(
            _Pet, filter={}, update={"$pull": {"tags": {"$in": ["a"]}}}
        ),
    ],
)
async def test_what_the_dialect_does_not_have_is_refused(database, store, call):
    with pytest.raises(QueryError):
        await call(database)

    assert store.calls == []


async def test_a_record_of_another_schema_is_refused(database):
    with pytest.raises(TypeError):
        await database.insert(_Pet, _Owner())


def test_a_storage_spec_naming_a_missing_field_fails_at_creation(store):
    class Broken(Schema):
        __storage__ = StorageSpec(table="broken", unique=("nmae",))

        id: Id = Field(default_factory=generate_id)

    with pytest.raises(UnknownFieldError):
        Database("memory://", schemas=[Broken])


def test_a_reference_to_a_schema_not_given_fails_at_creation(store):
    with pytest.raises(StorageSpecError):
        Database("memory://", schemas=[_Pet])


def test_an_indexed_list_that_is_not_a_list_fails_at_creation(store):
    class Broken(Schema):
        __storage__ = StorageSpec(table="broken", indexed_lists=("name",))

        id: Id = Field(default_factory=generate_id)
        name: str = ""

    with pytest.raises(StorageSpecError):
        Database("memory://", schemas=[Broken])


def test_a_schema_without_storage_spec_fails_at_creation(store):
    class Plain(Schema):
        id: Id = Field(default_factory=generate_id)

    with pytest.raises(StorageSpecError):
        Database("memory://", schemas=[Plain])


def test_a_url_no_store_supports_fails_at_creation():
    with pytest.raises(StorageError):
        Database("memory://", schemas=[_Owner])


class _Stray(Schema):
    __storage__ = StorageSpec(table="strays")

    id: Id = Field(default_factory=generate_id)


class _RecordingStore(DbStore):
    """Records each call, and finds whatever `found` holds"""

    def __init__(self):
        self.calls: List[tuple] = []
        self.found: List[Any] = []

    async def setup(self):
        self.calls.append(("setup",))

    async def get(self, schema, key):
        self.calls.append(("get", schema, {"key": key}))

    async def find(self, schema, query_filter, sort, skip, limit):
        call = {"filter": query_filter, "sort": sort, "skip": skip, "limit": limit}
        self.calls.append(("find", schema, call))
        return self.found

    async def count(self, schema, query_filter):
        self.calls.append(("count", schema, {"filter": query_filter}))
        return len(self.found)

    async def find_distinct(self, schema, field, query_filter):
        call = {"field": field, "filter": query_filter}
        self.calls.append(("find_distinct", schema, call))
        return []

    async def insert(self, schema, record):
        self.calls.append(("insert", schema, {"record": record}))
        return record

    async def insert_many(self, schema, records):
        self.calls.append(("insert_many", schema, {"records": records}))
        return list(records)

    async def update_one(self, schema, query_filter, update, should_upsert, returning):
        call = {"filter": query_filter, "update": update}
        self.calls.append(("update_one", schema, call))

    async def update_many(self, schema, query_filter, update):
        call = {"filter": query_filter, "update": update}
        self.calls.append(("update_many", schema, call))
        return 0

    async def delete_one(self, schema, query_filter):
        self.calls.append(("delete_one", schema, {"filter": query_filter}))

    async def delete_many(self, schema, query_filter):
        self.calls.append(("delete_many", schema, {"filter": query_filter}))
        return 0

    async def close(self):
        self.calls.append(("close",))


def test_parse_sort_reads_a_leading_minus_as_descending():
    assert parse_sort(["-created_at", "name"]) == [
        ("created_at", True),
        ("name", False),
    ]


async def test_a_schema_allowing_extra_fields_takes_undeclared_ones(store):
    class Open(Schema):
        __storage__ = StorageSpec(table="open")
        model_config = ConfigDict(extra="allow")

        id: Id = Field(default_factory=generate_id)

    database = Database("memory://", schemas=[Open])

    await database.update_many(
        Open, filter={"colour": "red"}, update={"$set": {"x": 1}}
    )

    assert store.calls[0][0] == "update_many"
