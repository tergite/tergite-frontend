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

from typing import List, Optional

import pytest
from pydantic import BaseModel, ValidationError

from libs.storage import Id, derive_id, generate_id
from libs.storage.base.ids import is_id_field


# computed with utils.crypto.generate_linked_id, which derive_id replaces
@pytest.mark.parametrize(
    "parent_id, namespace, expected",
    [
        ("8154077d9cb952b92453d575", "project", "5a0f3a453afbd14f180b7902"),
        ("de7ddbd2500951be940356a2", "project", "e8f6f63975e980b23e90b0ae"),
        ("5ddc8d9fb69602723cd3c38f", "other", "58ef0b92f203b6038dd5d3ee"),
        ("000000000000000000000000", "", "66096e87cc813a00bfb46efe"),
    ],
)
def test_derive_id_gives_the_ids_generate_linked_id_did(parent_id, namespace, expected):
    assert derive_id(parent_id, namespace) == expected


def test_generated_ids_are_time_ordered_ids():
    ids = [generate_id() for _ in range(100)]

    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)
    for value in ids:
        _Record(id=value)


@pytest.mark.parametrize(
    "value", ["", "ABCDEF0123456789abcdef01", "0123456789abcdef0123456", "x" * 24]
)
def test_an_id_is_24_lowercase_hex_characters(value):
    with pytest.raises(ValidationError):
        _Record(id=value)


def test_is_id_field_sees_ids_alone_and_in_containers():
    fields = _Record.model_fields

    assert [name for name in fields if is_id_field(fields[name])] == [
        "id",
        "ids",
        "maybe_id",
    ]


class _Record(BaseModel):
    id: Id
    ids: List[Id] = []
    maybe_id: Optional[Id] = None
    name: str = ""
