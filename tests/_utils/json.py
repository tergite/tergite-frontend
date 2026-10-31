# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Test utils for json"""
import dataclasses
import json
from typing import Any


class _EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


def to_json(value: Any, **kwargs) -> str:
    """Converts a value into a JSON string

    Args:
        value: the value to be converted into JSON
        kwargs: extra kwargs to pass to json.dumps

    Returns:
        JSON string representation of value
    """
    kwargs["cls"] = _EnhancedJSONEncoder
    return json.dumps(value, **kwargs)
