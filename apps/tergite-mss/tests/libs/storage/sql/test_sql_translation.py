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
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import pytest
from pydantic import BaseModel
from sqlalchemy import JSON, BigInteger, Boolean, Float, MetaData, String, select
from sqlalchemy.dialects import postgresql

from libs.storage import Id, QueryError, Schema, StorageSpec
from libs.storage.sql.tables import UtcDateTime, get_schema_tables
from libs.storage.sql.translate import translate_filter, translate_update

_OWNER_ID = "5ddc8d9fb69602723cd3c38f"


class _Colour(str, Enum):
    RED = "red"


class _Stats(BaseModel):
    walks: int = 0


class _Owner(Schema):
    __storage__ = StorageSpec(
        table="owners", unique=("email",), case_insensitive=("email",)
    )

    id: Id
    email: str


class _Pet(Schema):
    __storage__ = StorageSpec(
        table="pets",
        expires="expires_at",
        references={"owner_id": _Owner, "friend_ids": _Owner},
        indexed_lists=("tags",),
    )

    id: Id
    name: str
    age: int = 0
    weight: float = 0
    is_vaccinated: bool = False
    colour: Optional[_Colour] = None
    owner_id: Optional[Id] = None
    friend_ids: List[Id] = []
    tags: List[str] = []
    stats: _Stats = _Stats()
    extra: Dict[str, Any] = {}
    expires_at: Optional[datetime] = None


@pytest.fixture
def pets():
    return get_schema_tables(MetaData(), [_Pet, _Owner])[_Pet]


def test_scalars_get_columns_of_their_type_and_nested_fields_json(pets):
    columns = pets.table.c

    assert isinstance(columns["id"].type, String) and columns["id"].type.length == 24
    assert isinstance(columns["age"].type, BigInteger)
    assert isinstance(columns["weight"].type, Float)
    assert isinstance(columns["is_vaccinated"].type, Boolean)
    assert isinstance(columns["colour"].type, String)
    assert isinstance(columns["expires_at"].type, UtcDateTime)
    assert isinstance(columns["stats"].type, JSON)
    assert isinstance(columns["extra"].type, JSON)
    assert pets.json_fields == ("stats", "extra")
    assert columns["row_id"].primary_key and columns["id"].unique


def test_list_fields_get_child_tables(pets):
    tags = pets.list_tables["tags"]
    friends = pets.list_tables["friend_ids"]

    assert tags.table.name == "pet_tags"
    assert [column.name for column in tags.table.columns] == [
        "pet_id",
        "tag",
        "position",
    ]
    assert "tags" not in pets.table.c
    assert friends.table.name == "pet_friend_ids"
    (reference,) = friends.table.c["friend_id"].foreign_keys
    assert reference.column.table.name == "owners"
    (owner_reference,) = pets.table.c["owner_id"].foreign_keys
    assert owner_reference.column.table.name == "owners"


def test_a_case_insensitive_unique_field_is_unique_by_its_lower_case():
    metadata = MetaData()
    get_schema_tables(metadata, [_Owner])
    (index,) = metadata.tables["owners"].indexes

    assert index.unique
    assert str(index.expressions[0]) == "lower(owners.email)"


def test_filter_values_are_bound_parameters_never_sql_text(pets):
    hostile = "'; DROP TABLE pets; --"
    statement = select(pets.table.c.id).where(
        translate_filter(pets, {"name": hostile, "tags": {"$in": [hostile]}})
    )

    compiled = statement.compile(dialect=postgresql.dialect())

    assert hostile not in str(compiled)
    assert hostile in compiled.params.values()


@pytest.mark.parametrize(
    "query_filter",
    [
        {"stats.walks": 1},
        {"stats": {"walks": 1}},
        {"tags": ["a", "b"]},
        {"tags": {"$gt": "a"}},
    ],
)
def test_a_filter_into_json_or_on_a_whole_list_is_refused(pets, query_filter):
    with pytest.raises(QueryError):
        translate_filter(pets, query_filter)


def test_update_splits_into_column_values_and_child_writes(pets):
    changes = translate_update(
        pets,
        {
            "$set": {"name": "Rex", "stats": _Stats(walks=2), "tags": ["a"]},
            "$addToSet": {"friend_ids": _OWNER_ID},
            "$pull": {"tags": "b"},
            "$setOnInsert": {"colour": _Colour.RED},
        },
    )

    assert changes.values == {"name": "Rex", "stats": {"walks": 2}}
    assert changes.values_on_insert == {"colour": "red"}
    assert changes.list_replacements == {"tags": ["a"]}
    assert changes.list_additions == [("friend_ids", _OWNER_ID)]
    assert changes.list_removals == [("tags", "b")]


@pytest.mark.parametrize(
    "update",
    [
        {"$set": {"id": _OWNER_ID}},
        {"$inc": {"stats.walks": 1}},
        {"$addToSet": {"name": "x"}},
    ],
)
def test_an_update_of_the_key_into_json_or_of_a_scalar_list_is_refused(pets, update):
    with pytest.raises(QueryError):
        translate_update(pets, update)
