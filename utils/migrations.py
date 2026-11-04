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
"""Alembic's config for running the migrations in-process"""

from pathlib import Path
from typing import Optional

from alembic.config import Config

# beside main.py, in a checkout, a wheel and the Nuitka build
_MIGRATIONS_DIR = Path(__file__).parents[1] / "migrations"


def get_alembic_config(url: Optional[str] = None) -> Config:
    """Gets Alembic's config for the migrations, without alembic.ini, which a wheel cannot
    ship beside its packages

    Args:
        url: the URL of the database to migrate; default: the MSS config's

    Returns:
        the config, which leaves the process's logging as it is
    """
    config = Config()
    config.set_main_option("script_location", str(_MIGRATIONS_DIR))
    if url is not None:
        # the config interpolates %, as a URL's escapes have it
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config
