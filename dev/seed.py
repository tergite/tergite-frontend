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
"""Seeds the database of the MSS config with the dashboard's fixtures, clearing their tables first

Run from the repository root: `python -m dev.seed`. The e2e stack, its resets, the performance
checks and `npm run dev` all seed this way. It refuses a production config.
"""
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import settings
from libs.storage import Database
from services.auth import AppToken, DeletedProject, Project, User, ensure_roles
from services.calibration import DeviceCalibration, DeviceCalibrationLog
from services.devices import Device
from services.jobs import Job
from services.notices import Notice, NoticePreferences
from services.requests import Request
from services.schemas import SCHEMAS

FIXTURES_DIR = Path(__file__).parents[1] / "ui" / "fixtures"
# the system user's token, with which the e2e stack's backends call MSS
BOT_TOKEN = {
    "id": "67bdc2aacd991c8e1cf16ffc",
    "title": "some-token-test",
    "lifespan_seconds": 7200000,
    "token": "W0imS_n_J5ZwP8wFYvbBCiDkJVhQcEROEfyTPvFko1E",
}


def main() -> None:
    if settings.CONFIG.environment == "production":
        sys.exit("dev.seed: refusing to clear a production database")
    asyncio.run(seed(settings.CONFIG.database.full_url))


async def seed(database_url: str) -> None:
    """Clears the fixtures' tables, then fills them from the fixtures"""
    database = Database(database_url, schemas=SCHEMAS)
    await database.setup()
    try:
        await _clear(database)
        await _insert_fixtures(database)
    finally:
        await database.close()


async def _clear(database: Database) -> None:
    # the notice templates and roles stay, as MSS writes them only when it starts
    for schema in (
        AppToken,
        DeletedProject,
        Device,
        DeviceCalibration,
        DeviceCalibrationLog,
        Job,
        Notice,
        NoticePreferences,
        Project,
        Request,
        User,
    ):
        await database.delete_many(schema, {})


async def _insert_fixtures(database: Database) -> None:
    now = datetime.now(timezone.utc)
    users = _read("users")
    projects = _read("projects")
    await ensure_roles(database)
    await database.insert_many(User, [User.model_validate(v) for v in users])
    await database.insert_many(Project, [Project.model_validate(v) for v in projects])
    tokens = [{**v, "created_at": now} for v in _read("tokens")]
    tokens.append(_get_bot_token(users, projects, now))
    await database.insert_many(AppToken, [AppToken.model_validate(v) for v in tokens])
    await database.insert_many(
        DeviceCalibration,
        [DeviceCalibration.model_validate(v) for v in _read("calibrations")],
    )
    await database.insert_many(
        Device, [Device.model_validate(v) for v in _read("device-list")]
    )
    await database.insert_many(Job, [_get_job(v, now=now) for v in _read("jobs")])
    await database.insert_many(
        Notice, [_get_notice(v, now=now) for v in _read("notices")]
    )
    await database.insert_many(
        Request,
        [Request.model_validate(v) for v in _read("user-requests")],
    )


def _read(name: str) -> List[Dict[str, Any]]:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


def _get_bot_token(
    users: List[Dict[str, Any]], projects: List[Dict[str, Any]], now: datetime
) -> Dict[str, Any]:
    """Gets the system user's token, on an active project of theirs with QPU seconds"""
    bot = next(v for v in users if "system" in v["roles"])
    project = next(
        v
        for v in projects
        if bot["id"] in v["user_ids"] and v["qpu_seconds"] > 1 and v["is_active"]
    )
    return {
        **BOT_TOKEN,
        "user_id": bot["id"],
        "project_id": project["id"],
        "created_at": now,
    }


def _get_job(fixture: Dict[str, Any], now: datetime) -> Job:
    """Gets the job of the fixture: a successful one has results, and a timed one timestamps"""
    fields = {k: v for k, v in fixture.items() if k != "duration_in_secs"}
    if fixture["status"] == "successful":
        fields["result"] = {"memory": []}
        fields["download_url"] = f"http://{fixture['device']}/logfiles/{fixture['id']}"
    duration = fixture.get("duration_in_secs")
    if duration is not None:
        execution = {"started": now, "finished": now + timedelta(seconds=duration)}
        fields["timestamps"] = {"execution": execution}
    return Job.model_validate(fields)


def _get_notice(fixture: Dict[str, Any], now: datetime) -> Notice:
    """Gets the notice of the fixture, its times offset from now, so that it is as active as meant"""
    offsets = {
        "starts_at": fixture["starts_at_offset_hours"],
        "expires_at": fixture["expires_at_offset_hours"],
    }
    fields = {
        k: v
        for k, v in fixture.items()
        if k != "id" and not k.endswith("_offset_hours")
    }
    for field, hours in offsets.items():
        fields[field] = None if hours is None else now + timedelta(hours=hours)
    created_at = (now + timedelta(hours=fixture["created_at_offset_hours"])).isoformat()
    return Notice.model_validate(
        {**fields, "created_at": created_at, "updated_at": created_at}
    )


if __name__ == "__main__":
    main()
