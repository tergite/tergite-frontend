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
"""The migrations create exactly the tables SqlStore derives from the schemas"""
from pathlib import Path

from alembic import command
from alembic.config import Config

_APP_ROOT = Path(__file__).parent.parent


def test_the_migrations_match_the_schemas(tmp_path):
    """Fails when a schema changed without a migration: `alembic revision --autogenerate`"""
    config = Config(str(_APP_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_APP_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{tmp_path}/mss.db")

    command.upgrade(config, "head")
    command.check(config)
