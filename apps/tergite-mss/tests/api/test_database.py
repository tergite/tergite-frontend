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

import pytest

from api.database import get_database_url
from libs.storage import Database
from utils.config import DatabaseConfig


@pytest.mark.parametrize(
    "url, expected",
    [
        ("mongodb://localhost:27017", "mongodb://localhost:27017/tergite"),
        ("mongodb://localhost:27017/", "mongodb://localhost:27017/tergite"),
        ("mongodb://localhost:27017/other", "mongodb://localhost:27017/other"),
        (
            "mongodb+srv://user:pw@cluster.example.com/?retryWrites=true",
            "mongodb+srv://user:pw@cluster.example.com/tergite?retryWrites=true",
        ),
    ],
)
def test_the_database_name_fills_a_url_without_a_path(url, expected):
    assert get_database_url(DatabaseConfig(name="tergite", url=url)) == expected


def test_the_app_holds_one_database_while_it_runs(client, api_database):
    with client as client:
        database = client.app.state.database

        assert isinstance(database, Database)
        assert database.database_url == api_database.database.database_url
