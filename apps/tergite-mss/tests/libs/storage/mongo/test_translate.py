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

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import pymongo
import pytest
from bson import ObjectId
from pydantic import BaseModel

from libs.storage import (
    ALL,
    AddToSet,
    And,
    Contains,
    Eq,
    Id,
    In,
    Inc,
    Ne,
    NotIn,
    Or,
    Pull,
    Range,
    Schema,
    Set,
    SetOnInsert,
    Sort,
    StorageSpec,
)
from libs.storage.mongo.schema import CASE_INSENSITIVE, get_indexes, get_validator
from libs.storage.mongo.translate import (
    convert_to_document,
    convert_to_record,
    translate_filter,
    translate_sort,
    translate_update,
)

_OWNER_ID = "5ddc8d9fb69602723cd3c38f"
_OTHER_ID = "64f8a0c2b9d1e2f3a4b5c6d7"


class _Colour(str, Enum):
    RED = "red"


class _Timestamps(BaseModel):
    started: Optional[datetime] = None
    approver_id: Optional[Id] = None


class _Owner(Schema):
    __storage__ = StorageSpec(table="owners")

    id: Id


class _Pet(Schema):
    __storage__ = StorageSpec(
        table="pets",
        unique=("name",),
        case_insensitive=("name",),
        expires="expires_at",
        references={"owner_id": _Owner, "friend_ids": _Owner},
        indexed_lists=("tags",),
        indexes=(("owner_id", "-created_at"), "name"),
    )

    id: Id
    name: str
    owner_id: Optional[Id] = None
    friend_ids: List[Id] = []
    tags: List[str] = []
    colour: Optional[_Colour] = None
    timestamps: _Timestamps = _Timestamps()
    extra: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


@pytest.mark.parametrize(
    "where, expected",
    [
        (Eq("name", "Rex"), {"name": "Rex"}),
        (Eq("id", _OWNER_ID), {"_id": ObjectId(_OWNER_ID)}),
        (Eq("friend_ids", _OWNER_ID), {"friend_ids": ObjectId(_OWNER_ID)}),
        (Eq("owner_id", None), {"owner_id": None}),
        (Eq("colour", _Colour.RED), {"colour": "red"}),
        (
            Eq("timestamps.approver_id", _OWNER_ID),
            {"timestamps.approver_id": ObjectId(_OWNER_ID)},
        ),
        (Ne("name", "Rex"), {"name": {"$ne": "Rex"}}),
        (
            In("owner_id", [_OWNER_ID, _OTHER_ID]),
            {"owner_id": {"$in": [ObjectId(_OWNER_ID), ObjectId(_OTHER_ID)]}},
        ),
        (NotIn("tags", ["a"]), {"tags": {"$nin": ["a"]}}),
        (Range("created_at", gte=1, lt=5), {"created_at": {"$gte": 1, "$lt": 5}}),
        (Contains("name", "a.b"), {"name": {"$regex": r"a\.b"}}),
        (
            Contains("name", "rex", is_case_sensitive=False),
            {"name": {"$regex": "rex", "$options": "i"}},
        ),
        (ALL, {}),
        (And(Eq("name", "Rex")), {"name": "Rex"}),
        (
            And(Eq("name", "Rex"), Eq("tags", "a")),
            {"$and": [{"name": "Rex"}, {"tags": "a"}]},
        ),
        (
            Or(Eq("name", "Rex"), Eq("tags", "a")),
            {"$or": [{"name": "Rex"}, {"tags": "a"}]},
        ),
        (Or(), {"_id": {"$in": []}}),
    ],
)
def test_translate_filter(where, expected):
    assert translate_filter(_Pet, where) == expected


@pytest.mark.parametrize(
    "changes, expected",
    [
        ([Set("name", "Rex")], {"$set": {"name": "Rex"}}),
        (
            [Set("name", "Rex"), SetOnInsert("tags", ["a"])],
            {"$set": {"name": "Rex"}, "$setOnInsert": {"tags": ["a"]}},
        ),
        ([Inc("extra.count", 2)], {"$inc": {"extra.count": 2}}),
        (
            [AddToSet("friend_ids", _OWNER_ID)],
            {"$addToSet": {"friend_ids": ObjectId(_OWNER_ID)}},
        ),
        ([Pull("tags", "a")], {"$pull": {"tags": "a"}}),
    ],
)
def test_translate_update(changes, expected):
    assert translate_update(_Pet, changes) == expected


def test_translate_update_refuses_no_changes():
    with pytest.raises(ValueError):
        translate_update(_Pet, [])


def test_translate_sort():
    assert translate_sort([Sort("id"), Sort("created_at", is_descending=True)]) == [
        ("_id", pymongo.ASCENDING),
        ("created_at", pymongo.DESCENDING),
    ]


def test_a_record_and_its_document_convert_both_ways():
    started = datetime(2026, 1, 2, tzinfo=timezone.utc)
    record = _Pet(
        id=_OTHER_ID,
        name="Rex",
        owner_id=_OWNER_ID,
        friend_ids=[_OWNER_ID],
        colour=_Colour.RED,
        timestamps=_Timestamps(started=started, approver_id=_OWNER_ID),
    )

    document = convert_to_document(_Pet, record)

    assert document["_id"] == ObjectId(_OTHER_ID)
    assert "id" not in document
    assert document["owner_id"] == ObjectId(_OWNER_ID)
    assert document["friend_ids"] == [ObjectId(_OWNER_ID)]
    assert document["colour"] == "red"
    assert document["timestamps"] == {
        "started": started,
        "approver_id": ObjectId(_OWNER_ID),
    }
    assert convert_to_record(_Pet, document) == record


def test_indexes_follow_the_storage_facts():
    indexes = {
        tuple(index.document["key"].items()): index.document
        for index in get_indexes(_Pet)
    }

    assert indexes[(("name", 1),)]["unique"] is True
    assert indexes[(("name", 1),)]["collation"] == CASE_INSENSITIVE.document
    assert indexes[(("expires_at", 1),)]["expireAfterSeconds"] == 0
    assert (("friend_ids", 1),) in indexes
    assert (("tags", 1),) in indexes
    assert (("owner_id", 1), ("created_at", -1)) in indexes
    # owner_id is a scalar reference, which needs no index of its own here
    assert (("owner_id", 1),) not in indexes
    assert len(indexes) == 5


def test_the_validator_speaks_bson():
    properties = get_validator(_Pet)["$jsonSchema"]["properties"]

    assert properties["_id"] == {"bsonType": "objectId"}
    assert "id" not in properties
    assert {"bsonType": "objectId"} in properties["owner_id"]["anyOf"]
    assert properties["friend_ids"]["items"] == {"bsonType": "objectId"}
    assert {"bsonType": "date"} in properties["created_at"]["anyOf"]
