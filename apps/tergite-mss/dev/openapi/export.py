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

"""Writes the REST API's OpenAPI schema to openapi.json beside this file, without a server

Run from apps/tergite-mss: `python -m dev.openapi.export`. It works although production
serves no docs, since app.openapi() needs no route. The schema is built with the test config,
whose auth clients decide which /auth/{name} routes it lists.
"""
import json
from pathlib import Path

from tests._utils.env import setup_test_env

SCHEMA_FILE = Path(__file__).parent / "openapi.json"


def main():
    setup_test_env()
    from api import app  # settings read the environment set above on import

    SCHEMA_FILE.write_text(render_schema(app.openapi()))


def render_schema(schema: dict) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    main()
