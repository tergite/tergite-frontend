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
"""Runs every Database method against each database in the matrix, with the same results

MongoDB, PostgreSQL and SQLite each get a database of their own, emptied after every test.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pytest
from pydantic import BaseModel, Field
from pymongo import AsyncMongoClient

from libs.storage import (
    Database,
    DuplicateKeyError,
    Id,
    QueryError,
    Returning,
    Schema,
    StorageSpec,
    generate_id,
)
from tests._utils.env import TEST_MONGODB_URL
from tests._utils.storage import (
    SQL_DATABASE_KINDS,
    get_sql_database_url,
    reset_sql_database,
)

_MONGODB_NAME = "tergite-conformance-test"


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


class _Device(Schema):
    __storage__ = StorageSpec(table="devices", key="name")

    id: Id
    name: str
    version: str = ""


_SCHEMAS = [_Owner, _Pet, _Job, _Device]


@pytest.fixture(params=["mongodb", *SQL_DATABASE_KINDS])
async def database(request, tmp_path):
    if request.param == "mongodb":
        database_url = f"{TEST_MONGODB_URL.rstrip('/')}/{_MONGODB_NAME}"
    else:
        database_url = get_sql_database_url(request.param, tmp_path)
        await reset_sql_database(database_url)
    database = Database(database_url, schemas=_SCHEMAS)
    await database.setup()
    yield database
    await database.close()
    if request.param == "mongodb":
        client = AsyncMongoClient(TEST_MONGODB_URL)
        await client.drop_database(_MONGODB_NAME)
        await client.close()
    else:
        await reset_sql_database(database_url)


async def test_insert_and_get(database):
    owner = await database.insert(_Owner, _Owner(email="ann@example.com"))
    pet = await database.insert(_Pet, _Pet(name="Rex", owner_id=owner.id))

    assert await database.get(_Pet, pet.id) == pet
    assert await database.get(_Pet, generate_id()) is None


async def test_a_schema_keyed_by_another_field(database):
    await database.insert(_Job, _Job(job_id="j-1"))

    assert await database.get(_Job, "j-1") == _Job(job_id="j-1")
    with pytest.raises(DuplicateKeyError):
        await database.insert(_Job, _Job(job_id="j-1"))


async def test_unique_fields_refuse_duplicates(database):
    await database.insert(_Owner, _Owner(email="ann@example.com"))

    with pytest.raises(DuplicateKeyError):
        await database.insert(_Owner, _Owner(email="ANN@example.com"))
    with pytest.raises(DuplicateKeyError):
        await database.insert_many(
            _Owner, [_Owner(email="bob@example.com"), _Owner(email="Bob@example.com")]
        )


async def test_find_filters_sorts_and_pages(database):
    owner = await database.insert(_Owner, _Owner(email="ann@example.com"))
    names = ["a", "b", "c", "d"]
    await database.insert_many(
        _Pet,
        [_Pet(name=name, age=i, owner_id=owner.id) for i, name in enumerate(names)],
    )

    got = await database.find(
        _Pet, filter={"age": {"$gte": 1}}, sort=["-age"], skip=1, limit=2
    )
    either = {"$or": [{"name": "a"}, {"age": {"$gt": 2}}]}

    assert [pet.name for pet in got] == ["c", "b"]
    assert [pet.name for pet in await database.find(_Pet)] == names
    assert await database.count(_Pet, filter={"owner_id": owner.id}) == 4
    assert await database.count(_Pet, filter=either) == 2
    assert (await database.find_one(_Pet, filter={"name": {"$in": ["d"]}})).age == 3
    assert await database.find_distinct(_Pet, "owner_id") == [owner.id]


async def test_none_matches_a_null_field_as_mongodb_does(database):
    owner = await database.insert(_Owner, _Owner(email="ann@example.com"))
    await database.insert(_Pet, _Pet(name="Rex", owner_id=owner.id))
    await database.insert(_Pet, _Pet(name="Max"))

    async def find_names(pet_filter):
        return sorted(pet.name for pet in await database.find(_Pet, pet_filter))

    assert await find_names({"owner_id": None}) == ["Max"]
    assert await find_names({"owner_id": {"$ne": owner.id}}) == ["Max"]
    assert await find_names({"owner_id": {"$ne": None}}) == ["Rex"]
    assert await find_names({"owner_id": {"$in": [owner.id, None]}}) == ["Max", "Rex"]
    assert await find_names({"owner_id": {"$nin": [owner.id]}}) == ["Max"]
    assert await find_names({"owner_id": {"$nin": [None]}}) == ["Rex"]


async def test_case_insensitive_fields_match_without_case(database):
    await database.insert(_Owner, _Owner(email="ann@example.com"))

    assert await database.count(_Owner, filter={"email": "ANN@EXAMPLE.COM"}) == 1
    assert await database.count(_Owner, filter={"email": {"$in": ["Ann@x.y"]}}) == 0


async def test_update_one_returns_the_record_before_or_after(database):
    pet = await database.insert(_Pet, _Pet(name="Rex"))

    before = await database.update_one(
        _Pet,
        filter={"id": pet.id},
        update={"$inc": {"age": 1}},
        returning=Returning.BEFORE,
    )
    after = await database.update_one(
        _Pet, filter={"id": pet.id}, update={"$set": {"stats": {"walks": 2}}}
    )
    missing = await database.update_one(
        _Pet, filter={"name": "Nobody"}, update={"$set": {"age": 1}}
    )

    assert before.age == 0
    assert after.age == 1 and after.stats.walks == 2
    assert missing is None


async def test_an_update_may_set_the_key_it_has_but_not_another(database):
    await database.insert(_Job, _Job(job_id="j-1"))

    same = await database.update_one(
        _Job, {"job_id": "j-1"}, {"$set": {"job_id": "j-1", "status": "done"}}
    )

    assert same == _Job(job_id="j-1", status="done")
    with pytest.raises(QueryError):
        await database.update_one(_Job, {"job_id": "j-1"}, {"$set": {"job_id": "j-2"}})


async def test_an_upsert_generates_the_id_of_a_schema_keyed_by_another_field(database):
    created = await database.update_one(
        _Device,
        filter={"name": "Loke"},
        update={"$set": {"name": "Loke", "version": "1"}},
        should_upsert=True,
    )

    assert created.name == "Loke" and len(created.id) == 24
    assert await database.get(_Device, "Loke") == created


async def test_update_one_upserts(database):
    created = await database.update_one(
        _Job,
        filter={"job_id": "j-2"},
        update={"$set": {"status": "done"}, "$setOnInsert": {"job_id": "j-2"}},
        should_upsert=True,
    )
    updated = await database.update_one(
        _Job,
        filter={"job_id": "j-2"},
        update={"$set": {"status": "failed"}, "$setOnInsert": {"job_id": "j-2"}},
        should_upsert=True,
    )

    assert created == _Job(job_id="j-2", status="done")
    assert updated == _Job(job_id="j-2", status="failed")
    assert await database.count(_Job) == 1


async def test_list_fields_take_and_drop_members(database):
    friend = await database.insert(_Owner, _Owner(email="bob@example.com"))
    other = await database.insert(_Owner, _Owner(email="cat@example.com"))
    pet = await database.insert(_Pet, _Pet(name="Rex", friend_ids=[other.id]))

    pet_filter = {"id": pet.id}
    await database.update_many(
        _Pet, pet_filter, {"$addToSet": {"friend_ids": friend.id}}
    )
    count = await database.update_many(
        _Pet, pet_filter, {"$addToSet": {"friend_ids": friend.id}}
    )
    assert count == 0
    assert (await database.get(_Pet, pet.id)).friend_ids == [other.id, friend.id]
    assert await database.count(_Pet, filter={"friend_ids": friend.id}) == 1
    assert await database.count(_Pet, filter={"friend_ids": {"$nin": [friend.id]}}) == 0

    count = await database.update_many(
        _Pet, pet_filter, {"$pull": {"friend_ids": friend.id}}
    )
    assert count == 1
    assert (await database.get(_Pet, pet.id)).friend_ids == [other.id]

    await database.update_many(_Pet, pet_filter, {"$set": {"friend_ids": [friend.id]}})
    assert (await database.get(_Pet, pet.id)).friend_ids == [friend.id]


async def test_delete_one_and_many(database):
    rex = await database.insert(_Pet, _Pet(name="Rex"))
    await database.insert_many(_Pet, [_Pet(name="a", age=1), _Pet(name="b", age=1)])

    assert await database.delete_one(_Pet, {"id": rex.id}) == rex
    assert await database.delete_one(_Pet, {"id": rex.id}) is None
    assert await database.delete_many(_Pet, {"age": 1}) == 2
    assert await database.count(_Pet) == 0


async def test_expiring_records_carry_a_datetime(database):
    expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    pet = await database.insert(_Pet, _Pet(name="Rex", expires_at=expires_at))

    got = await database.get(_Pet, pet.id)

    assert abs(got.expires_at - expires_at) < timedelta(milliseconds=1)
