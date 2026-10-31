# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Module containing utilities related to types"""

from pydantic._internal._generate_schema import GenerateSchema
from pydantic_core import core_schema

_ORIGINAL_GENERATE_SCHEMA_MATCH_TYPE = GenerateSchema.match_type


def stub_pydantic_match_type_for_freezegun():
    """
    Fixes pydantic to work well with Freezegun datetimes

    https://github.com/pydantic/pydantic/discussions/9343#discussioncomment-10723743
    """

    # *args: pydantic>=2.14 also passes the origin of obj
    def match_type(self, obj, *args):
        if getattr(obj, "__name__", None) == "datetime":
            return core_schema.datetime_schema()
        return _ORIGINAL_GENERATE_SCHEMA_MATCH_TYPE(self, obj, *args)

    GenerateSchema.match_type = match_type


def remove_pydantic_match_type_freezegun_stub():
    """
    Removes the stub for pydantic integration with Freezegun datetimes
    """
    GenerateSchema.match_type = _ORIGINAL_GENERATE_SCHEMA_MATCH_TYPE
