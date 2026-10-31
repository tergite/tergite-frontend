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

from libs.storage.mongo.schema import (
    _map_to_bson_type,
    _resolve_ref,
    _translate_keywords,
)


def test_a_reference_takes_its_definition_under_its_own_keys():
    definitions = {"Thing": {"type": "object", "title": "Thing"}}

    schema = _resolve_ref(
        {"$ref": "#/$defs/Thing", "title": "Own"}, definitions=definitions
    )

    assert schema == {"type": "object", "title": "Own"}


def test_exclusive_bounds_become_draft_4_booleans():
    assert _translate_keywords({"exclusiveMinimum": 0, "const": "a"}) == {
        "exclusiveMinimum": True,
        "minimum": 0,
        "const": "a",
        "enum": ["a"],
    }


def test_dates_and_ids_become_their_bson_types():
    assert _map_to_bson_type({"type": "string", "format": "date-time"}) == {
        "bsonType": "date"
    }
    assert _map_to_bson_type({"type": "string", "pattern": "^[0-9a-f]{24}$"}) == {
        "bsonType": "objectId"
    }
    assert _map_to_bson_type({"type": "integer"}) == {
        "type": "integer",
        "bsonType": ["int", "long"],
    }
