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

"""What only MongoStore does: ObjectIds, nested updates, indexes and validators

What every store does alike is in tests/libs/storage/test_conformance.py.
"""
from datetime import datetime
from typing import List, Optional

import pytest
from bson import ObjectId
from pydantic import BaseModel, Field
from pymongo import AsyncMongoClient, IndexModel
from pymongo.errors import WriteError

from libs.storage import Database, Id, Schema, StorageSpec, generate_id
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


async def test_ids_are_stored_as_object_ids(database, raw):
    owner = await database.insert(_Owner, _Owner(email="ann@example.com"))
    pet = await database.insert(_Pet, _Pet(name="Rex", owner_id=owner.id))

    document = await raw["pets"].find_one({"_id": ObjectId(pet.id)})

    assert document["owner_id"] == ObjectId(owner.id)
    assert await database.get(_Pet, pet.id) == pet


async def test_a_nested_field_is_updated_in_place(database):
    pet = await database.insert(_Pet, _Pet(name="Rex"))

    updated = await database.update_one(
        _Pet, filter={"id": pet.id}, update={"$inc": {"stats.walks": 1}}
    )

    assert updated.stats.walks == 1


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
