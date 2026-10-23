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
"""Test utilities for the SQL databases the storage layer runs on"""
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests._utils.env import TEST_POSTGRES_URL

SQL_DATABASE_KINDS = ("postgresql", "sqlite")


def get_sql_database_url(kind: str, tmp_path: Path) -> str:
    """Gets the URL of a database of the kind: the test PostgreSQL, or a new SQLite file"""
    if kind == "postgresql":
        return TEST_POSTGRES_URL
    return f"sqlite+aiosqlite:///{tmp_path}/test.db"


async def reset_sql_database(database_url: str) -> None:
    """Drops every table of a shared database, so the next test derives its own

    A SQLite file is new to each test, so only PostgreSQL needs this.
    """
    if not database_url.startswith("postgresql"):
        return
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()
