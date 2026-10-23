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

"""Runs every Database method against a real MongoDB, in a database of its own"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pytest
from bson import ObjectId
from pydantic import BaseModel, Field
from pymongo import AsyncMongoClient, IndexModel
from pymongo.errors import WriteError

from libs.storage import (
    AddToSet,
    Contains,
    Database,
    DuplicateKeyError,
    Eq,
    Id,
    In,
    Inc,
    Page,
    Pull,
    Range,
    Returning,
    Schema,
    Set,
    SetOnInsert,
    Sort,
    StorageSpec,
    generate_id,
)
from tests._utils.env import TEST_MONGODB_URL

_DATABASE_NAME = "tergite-storage-test"
_DATABASE_URL = f"{TEST_MONGODB_URL.rstrip('/')}/{_DATABASE_NAME}"


class _Owner(Schema):
    __storage__ = StorageSpec(
        table="owners", unique=("email",), case_insensitive=("email",)
    )

    id: Id = Field(default_factory=generate_id)
    email: str


class _Stats(BaseModel):
    walks: int = 0


class _Pet(Schema):
    __storage__ = StorageSpec(
        table="pets",
        unique=("name",),
        expires="expires_at",
        references={"owner_id": _Owner, "friend_ids": _Owner},
        indexes=(("owner_id", "-age"),),
    )

    id: Id = Field(default_factory=generate_id)
    name: str
    age: int = 0
    owner_id: Optional[Id] = None
    friend_ids: List[Id] = []
    stats: _Stats = _Stats()
    expires_at: Optional[datetime] = None


class _Job(Schema):
    __storage__ = StorageSpec(table="jobs", key="job_id", unique=("job_id",))

    job_id: str
    status: str = "pending"


@pytest.fixture
async def raw():
    """The test database, reached around the storage layer to see what it stored"""
    client = AsyncMongoClient(TEST_MONGODB_URL, tz_aware=True)
    yield client[_DATABASE_NAME]
    await client.close()


@pytest.fixture
async def database():
    database = Database(_DATABASE_URL, schemas=[_Owner, _Pet, _Job])
    await database.setup()
    yield database
    await database.close()
    client = AsyncMongoClient(TEST_MONGODB_URL)
    await client.drop_database(_DATABASE_NAME)
    await client.close()


async def test_insert_and_get(database, raw):
    owner = await database.insert(_Owner, _Owner(email="ann@example.com"))
    pet = await database.insert(_Pet, _Pet(name="Rex", owner_id=owner.id))

    assert await database.get(_Pet, pet.id) == pet
    assert await database.get(_Pet, generate_id()) is None
    assert (await raw["pets"].find_one({"_id": ObjectId(pet.id)}))["owner_id"] == (
        ObjectId(owner.id)
    )


async def test_a_schema_keyed_by_another_field(database):
    await database.insert(_Job, _Job(job_id="j-1"))

    assert await database.get(_Job, "j-1") == _Job(job_id="j-1")


async def test_unique_fields_refuse_duplicates(database):
    await database.insert(_Owner, _Owner(email="ann@example.com"))

    with pytest.raises(DuplicateKeyError):
        await database.insert(_Owner, _Owner(email="ANN@example.com"))
    with pytest.raises(DuplicateKeyError):
        await database.insert_many(
            _Owner, [_Owner(email="bob@example.com"), _Owner(email="Bob@example.com")]
        )


async def test_find_filters_sorts_and_pages(database):
    owner_id = generate_id()
    names = ["a", "b", "c", "d"]
    await database.insert_many(
        _Pet,
        [_Pet(name=name, age=i, owner_id=owner_id) for i, name in enumerate(names)],
    )

    got = await database.find(
        _Pet,
        where=Range("age", gte=1),
        sort=[Sort("age", is_descending=True)],
        page=Page(skip=1, limit=2),
    )

    assert [pet.name for pet in got] == ["c", "b"]
    assert await database.count(_Pet, where=Eq("owner_id", owner_id)) == 4
    assert (await database.find_one(_Pet, where=In("name", ["d"]))).age == 3
    assert await database.find_distinct(_Pet, "owner_id") == [owner_id]


async def test_case_insensitive_fields_match_without_case(database):
    await database.insert(_Owner, _Owner(email="ann@example.com"))

    assert await database.count(_Owner, where=Eq("email", "ANN@EXAMPLE.COM")) == 1
    assert await database.count(_Owner, where=Contains("email", "ANN", False)) == 1
    assert await database.count(_Owner, where=Contains("email", "ANN")) == 0


async def test_update_one_returns_the_record_before_or_after(database):
    pet = await database.insert(_Pet, _Pet(name="Rex"))

    before = await database.update_one(
        _Pet,
        where=Eq("id", pet.id),
        changes=[Inc("stats.walks", 1)],
        returning=Returning.BEFORE,
    )
    after = await database.update_one(
        _Pet, where=Eq("id", pet.id), changes=[Set("age", 4)]
    )

    assert before.stats.walks == 0
    assert after.stats.walks == 1 and after.age == 4
    assert (
        await database.update_one(_Pet, Eq("name", "Nobody"), [Set("age", 1)]) is None
    )


async def test_update_one_upserts(database):
    created = await database.update_one(
        _Job,
        where=Eq("job_id", "j-2"),
        changes=[Set("status", "done"), SetOnInsert("job_id", "j-2")],
        should_upsert=True,
    )

    assert created == _Job(job_id="j-2", status="done")


async def test_list_fields_take_and_drop_members(database):
    friend_id = generate_id()
    pet = await database.insert(_Pet, _Pet(name="Rex"))

    await database.update_many(
        _Pet, Eq("id", pet.id), [AddToSet("friend_ids", friend_id)]
    )
    await database.update_many(
        _Pet, Eq("id", pet.id), [AddToSet("friend_ids", friend_id)]
    )
    assert (await database.get(_Pet, pet.id)).friend_ids == [friend_id]
    assert await database.count(_Pet, where=Eq("friend_ids", friend_id)) == 1

    count = await database.update_many(
        _Pet, Eq("id", pet.id), [Pull("friend_ids", friend_id)]
    )
    assert count == 1
    assert (await database.get(_Pet, pet.id)).friend_ids == []


async def test_delete_one_and_many(database):
    rex = await database.insert(_Pet, _Pet(name="Rex"))
    await database.insert_many(_Pet, [_Pet(name="a", age=1), _Pet(name="b", age=1)])

    assert await database.delete_one(_Pet, Eq("id", rex.id)) == rex
    assert await database.delete_one(_Pet, Eq("id", rex.id)) is None
    assert await database.delete_many(_Pet, Eq("age", 1)) == 2
    assert await database.count(_Pet) == 0


async def test_setup_makes_the_indexes_the_storage_facts_ask_for(database, raw):
    indexes = {
        tuple(info["key"].items()): info
        async for info in await raw["pets"].list_indexes()
    }

    assert indexes[(("name", 1),)]["unique"] is True
    assert indexes[(("expires_at", 1),)]["expireAfterSeconds"] == 0
    assert (("friend_ids", 1),) in indexes
    assert (("owner_id", 1), ("age", -1)) in indexes
    owners = {
        tuple(info["key"].items()): info
        async for info in await raw["owners"].list_indexes()
    }
    assert owners[(("email", 1),)]["collation"]["strength"] == 2


async def test_setup_replaces_an_index_whose_options_changed(database, raw):
    await raw["pets"].drop_index("name_1")
    await raw["pets"].create_indexes([IndexModel("name", sparse=True)])

    await database.setup()
    await database.setup()

    indexes = {info["name"]: info async for info in await raw["pets"].list_indexes()}
    assert indexes["name_1"]["unique"] is True
    assert "sparse" not in indexes["name_1"]


async def test_the_validator_rejects_documents_off_the_schema(database, raw):
    with pytest.raises(WriteError):
        await raw["pets"].insert_one({"name": 7})


async def test_expiring_records_carry_a_datetime(database):
    expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    pet = await database.insert(_Pet, _Pet(name="Rex", expires_at=expires_at))

    got = await database.get(_Pet, pet.id)

    assert abs(got.expires_at - expires_at) < timedelta(milliseconds=1)
