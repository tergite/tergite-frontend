# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Test utilities for environment variables"""
import json
import tomllib
from os import environ
from pathlib import Path
from typing import Dict, List, NotRequired, TypedDict

from .fixtures import get_fixture_path

TEST_MSS_CONFIG_FILE = get_fixture_path("config.test.toml")

with Path(TEST_MSS_CONFIG_FILE).open(mode="rb") as _oauth_conf_file:
    TEST_APP_CONFIG = tomllib.load(_oauth_conf_file)
    TEST_MSS_CONFIG_JSON_STR = json.dumps(TEST_APP_CONFIG)

TEST_MSS_PUBLIC_KEY_PATH = get_fixture_path("mss_public_key.pem")
TEST_MSS_PRIVATE_KEY_PATH = get_fixture_path("mss_private_key.pem")

TEST_DB_NAME: str = TEST_APP_CONFIG["database"]["name"]
TEST_MONGODB_URL: str = TEST_APP_CONFIG["database"]["url"]
TEST_REDIS_URL: str = TEST_APP_CONFIG["database"]["redis_url"]
# the conformance tests' PostgreSQL, which no app test uses yet
TEST_POSTGRES_URL: str = environ.get(
    "TEST_POSTGRES_URL",
    "postgresql+asyncpg://tergite:tergite@localhost:5432/tergite_test",
)
# the database the API tests run the app on; a SQL URL runs them on SQL, so it must not
# be the storage tests' PostgreSQL database, which they empty per test
TEST_DATABASE_URL: str = environ.get(
    "TEST_DATABASE_URL", f"{TEST_MONGODB_URL.rstrip('/')}/{TEST_DB_NAME}"
)
TEST_JWT_SECRET: str = TEST_APP_CONFIG["auth"]["jwt_secret"]
TEST_BACKENDS: List["BackendConfDict"] = TEST_APP_CONFIG["backends"]
TEST_BACKENDS_MAP: Dict[str, "BackendConfDict"] = {
    item["name"]: item for item in TEST_BACKENDS
}


def setup_test_env():
    """Sets up the test environment.

    It should be run before any imports
    """
    environ["MSS_CONFIG_JSON_STR"] = TEST_MSS_CONFIG_JSON_STR
    environ["PRIVATE_KEY_FILE"] = TEST_MSS_PRIVATE_KEY_PATH


class BackendConfDict(TypedDict):
    name: str
    url: str
    public_url: NotRequired[str]
