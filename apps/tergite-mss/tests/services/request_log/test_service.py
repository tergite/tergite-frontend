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

from datetime import timedelta

import pytest

from libs.storage import ALL, Database
from services import request_log
from services.request_log import RequestLog
from tests._utils.env import TEST_MONGODB_URL

_DATABASE_NAME = "tergite-request-log-test"


@pytest.fixture
async def database():
    database = Database(f"{TEST_MONGODB_URL}/{_DATABASE_NAME}", schemas=[RequestLog])
    await database.setup()
    yield database
    await database.delete_many(RequestLog, where=ALL)
    await database.close()


async def test_a_request_id_is_new_once(database):
    assert await request_log.record_request(database, "r-1", ttl=60) is True
    assert await request_log.record_request(database, "r-1", ttl=60) is False
    assert await request_log.is_request_recorded(database, "r-1") is True
    assert await request_log.is_request_recorded(database, "r-2") is False


async def test_a_record_expires_after_its_ttl(database):
    await request_log.record_request(database, "r-1", ttl=90, client_name="Loke")

    log = await database.find_one(RequestLog)

    assert log.client_name == "Loke"
    assert log.expires_at - log.created_at == timedelta(seconds=90)
