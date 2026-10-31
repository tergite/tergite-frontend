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

"""The app's one Database: opened in the lifespan, handed to routes through DatabaseDep"""
from fastapi import FastAPI
from starlette.requests import HTTPConnection

from libs.storage import Database
from services.schemas import SCHEMAS
from utils.config import DatabaseConfig


async def open_database(app: FastAPI, conf: DatabaseConfig) -> Database:
    """Opens the Database with every service's schemas and keeps it on the app's state

    Args:
        app: the FastAPI app to keep the database on
        conf: the database's configuration

    Returns:
        the opened database
    """
    database = Database(conf.full_url, schemas=SCHEMAS)
    await database.setup()
    app.state.database = database
    return database


async def close_database(app: FastAPI) -> None:
    """Closes the Database kept on the app's state

    Args:
        app: the FastAPI app the database was opened on
    """
    await app.state.database.close()


def get_database(connection: HTTPConnection) -> Database:
    """Dependency injector of the app's Database, for HTTP routes and websockets alike

    Args:
        connection: the current HTTP request or websocket

    Returns:
        the app's database
    """
    return connection.app.state.database
