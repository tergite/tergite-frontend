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
"""The jobs service on each SQL database: JSON timestamps and results, finds and counts"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from libs.storage import Database, generate_id
from services import jobs
from services.jobs import Job, JobQuery
from services.jobs.dtos import JobStatus, JobTimestamps, JobUpdate, TimestampPair

_USER_ID = generate_id()
_STARTED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


@pytest.fixture
async def database(sql_database_url):
    database = Database(sql_database_url, schemas=jobs.SCHEMAS)
    await database.setup()
    yield database
    await database.close()


async def test_a_job_with_timestamps_round_trips(database):
    execution = TimestampPair(
        started=_STARTED, finished=_STARTED + timedelta(seconds=3)
    )
    job = _get_job(
        device="Loke", user_id=_USER_ID, timestamps=JobTimestamps(execution=execution)
    )
    await database.insert(Job, job)

    got = await jobs.get_job(database, job.job_id)

    assert got == job
    assert got.duration_in_secs == 3


async def test_update_job_returns_the_job_as_it_was(database):
    job = _get_job(device="Loke")
    await database.insert(Job, job)

    before = await jobs.update_job(
        database, job.job_id, JobUpdate(status=JobStatus.SUCCESSFUL, download_url="u")
    )
    after = await jobs.get_job(database, job.job_id)

    assert before.status == JobStatus.PENDING
    assert (after.status, after.download_url) == (JobStatus.SUCCESSFUL, "u")


async def test_jobs_are_found_by_query_owner_and_reader(database):
    own = _get_job(device="Loke", user_id=_USER_ID)
    unowned = _get_job(device="Loke")
    others = _get_job(device="Pingu", user_id=generate_id())
    for job in (own, unowned, others):
        await database.insert(Job, job)
    reader = SimpleNamespace(id=_USER_ID, is_superuser=False)

    def get_ids(found):
        return sorted(job.job_id for job in found)

    by_device = await jobs.get_latest_many(database, JobQuery(device="Loke"))
    by_owner = await jobs.get_latest_many(database, JobQuery(), user_id=_USER_ID)
    readable = await jobs.get_latest_many(database, JobQuery(), reader=reader)

    assert get_ids(by_device) == get_ids([own, unowned])
    assert get_ids(by_owner) == [own.job_id]
    assert get_ids(readable) == get_ids([own, unowned])
    assert all(job.access_token is None for job in readable)


async def test_submitters_are_counted_in_a_window(database):
    for user_id in (_USER_ID, _USER_ID, None):
        await database.insert(Job, _get_job(device="Loke", user_id=user_id))
    start = datetime.now(timezone.utc) - timedelta(minutes=1)
    end = datetime.now(timezone.utc) + timedelta(minutes=1)

    assert await jobs.count_job_submitters(database, start, end) == 1
    assert await jobs.count_job_submitters(database, start, end, False) == 3


def _get_job(**fields) -> Job:
    return Job(calibration_date="2026-01-01T00:00:00.000Z", **fields)
