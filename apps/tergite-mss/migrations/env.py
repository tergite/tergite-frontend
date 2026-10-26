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
"""Alembic's environment: the tables SqlStore derives, at the configured database's URL

Run from apps/tergite-mss with the MSS config in the environment, as main.py migrate does:
`alembic upgrade head`, or `alembic revision --autogenerate -m "..."` against an up-to-date
database after a schema changes. Review a generated revision by hand before committing it.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import settings
from libs.storage.sql import get_metadata
from services.schemas import SCHEMAS

if context.config.config_file_name is not None:
    # run in-process too, as by the tests, where it must not silence the app's loggers
    fileConfig(context.config.config_file_name, disable_existing_loggers=False)

target_metadata = get_metadata(SCHEMAS)
# a URL set in Alembic's config, as tests set one, stands in for the MSS config's
database_url = (
    context.config.get_main_option("sqlalchemy.url")
    or settings.CONFIG.database.full_url
)


def run_migrations_offline() -> None:
    """Writes the migrations as SQL instead of running them"""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        user_module_prefix="libs.storage.sql.tables.",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        user_module_prefix="libs.storage.sql.tables.",
        # SQLite alters a table only by copying it
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
