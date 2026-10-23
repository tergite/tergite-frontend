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
from typing import Tuple, Type
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from starlette.requests import HTTPConnection

from libs.storage import Database, Schema
from services import auth, calibration, devices, jobs, notices, request_log, requests
from utils.config import DatabaseConfig

# each service adds its schemas here as it moves onto the storage layer
SCHEMAS: Tuple[Type[Schema], ...] = (
    *auth.SCHEMAS,
    *calibration.SCHEMAS,
    *devices.SCHEMAS,
    *jobs.SCHEMAS,
    *notices.SCHEMAS,
    *request_log.SCHEMAS,
    *requests.SCHEMAS,
)


async def open_database(app: FastAPI, conf: DatabaseConfig) -> Database:
    """Opens the Database with every service's schemas and keeps it on the app's state"""
    database = Database(get_database_url(conf), schemas=SCHEMAS)
    await database.setup()
    app.state.database = database
    return database


def open_users_database(app: FastAPI, conf: DatabaseConfig) -> AsyncIOMotorDatabase:
    """Opens the Motor database Beanie keeps the users in, until they move onto the Database"""
    client = AsyncIOMotorClient(get_database_url(conf), tz_aware=True)
    app.state.users_client = client
    return client.get_default_database()


async def close_database(app: FastAPI) -> None:
    await app.state.database.close()
    app.state.users_client.close()


def get_database(connection: HTTPConnection) -> Database:
    """Dependency injector of the app's Database, for HTTP routes and websockets alike"""
    return connection.app.state.database


def get_database_url(conf: DatabaseConfig) -> str:
    """Gets the URL of the configured database: its url, with the name as the path if it has none"""
    parts = urlsplit(str(conf.url))
    if parts.path in ("", "/"):
        parts = parts._replace(path=f"/{conf.name}")
    return urlunsplit(parts)
