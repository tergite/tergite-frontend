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

from api import app
from dev.openapi.export import SCHEMA_FILE, render_schema
from dev.openapi.generate import MODELS_FILE, render_models


def test_committed_schema_matches_the_app():
    assert SCHEMA_FILE.read_text() == render_schema(app.openapi()), (
        f"{SCHEMA_FILE.name} is stale: run python -m dev.openapi.export"
    )


def test_backend_event_models_match_its_spec():
    """A changed spec, or a hand-edited model, fails until the models are regenerated"""
    assert MODELS_FILE.read_text() == render_models(), (
        f"{MODELS_FILE.name} is stale: run dev/openapi/sync.sh"
    )
