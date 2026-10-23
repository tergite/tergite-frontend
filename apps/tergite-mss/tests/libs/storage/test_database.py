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
from pydantic import BaseModel, Field

from libs.storage import (
    ALL,
    And,
    Database,
    Eq,
    Id,
    Page,
    Schema,
    Set,
    Sort,
    StorageError,
    StorageSpec,
    StorageSpecError,
    UnknownFieldError,
    UnknownSchemaError,
    generate_id,
)
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
    where = And(Eq("name", "Rex"), Eq("timestamps.started", None))

    await database.find(_Pet, where=where, sort=[Sort("name")], page=Page(skip=1))
    await database.update_many(_Pet, where=ALL, changes=[Set("extra.colour", "red")])

    assert store.calls == [
        ("find", _Pet, {"where": where, "sort": [Sort("name")], "page": Page(skip=1)}),
        ("update_many", _Pet, {"where": ALL, "changes": [Set("extra.colour", "red")]}),
    ]


async def test_find_one_asks_for_one_record(database, store):
    store.found = [_Pet(name="Rex")]

    got = await database.find_one(_Pet, where=Eq("name", "Rex"))

    assert got is store.found[0]
    assert store.calls[0][2]["page"] == Page(limit=1)


@pytest.mark.parametrize(
    "call",
    [
        lambda db: db.get(_Stray, generate_id()),
        lambda db: db.find(_Stray),
        lambda db: db.count(_Stray),
        lambda db: db.delete_many(_Stray, where=ALL),
    ],
)
async def test_a_schema_the_database_was_not_given_is_refused(database, call):
    with pytest.raises(UnknownSchemaError):
        await call(database)


@pytest.mark.parametrize(
    "call",
    [
        lambda db: db.find(_Pet, where=Eq("nmae", "Rex")),
        lambda db: db.find(_Pet, sort=[Sort("timestamps.ended")]),
        lambda db: db.update_many(_Pet, where=ALL, changes=[Set("tag", "x")]),
        lambda db: db.find_distinct(_Pet, "owner"),
    ],
)
async def test_a_field_the_schema_does_not_have_is_refused(database, store, call):
    with pytest.raises(UnknownFieldError):
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

    async def find(self, schema, where=ALL, sort=(), page=Page()):
        self.calls.append(
            ("find", schema, {"where": where, "sort": sort, "page": page})
        )
        return self.found

    async def count(self, schema, where=ALL):
        self.calls.append(("count", schema, {"where": where}))
        return len(self.found)

    async def find_distinct(self, schema, field, where=ALL):
        self.calls.append(("find_distinct", schema, {"field": field, "where": where}))
        return []

    async def insert(self, schema, record):
        self.calls.append(("insert", schema, {"record": record}))
        return record

    async def insert_many(self, schema, records):
        self.calls.append(("insert_many", schema, {"records": records}))
        return list(records)

    async def update_one(self, schema, where, changes, should_upsert, returning):
        self.calls.append(("update_one", schema, {"where": where, "changes": changes}))

    async def update_many(self, schema, where, changes):
        self.calls.append(("update_many", schema, {"where": where, "changes": changes}))
        return 0

    async def delete_one(self, schema, where):
        self.calls.append(("delete_one", schema, {"where": where}))

    async def delete_many(self, schema, where):
        self.calls.append(("delete_many", schema, {"where": where}))
        return 0

    async def close(self):
        self.calls.append(("close",))
