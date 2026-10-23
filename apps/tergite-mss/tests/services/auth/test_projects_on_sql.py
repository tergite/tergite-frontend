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
"""ProjectDatabase on each SQL database: projects, their members' table and deletions"""
from types import SimpleNamespace

import pytest

from libs.storage import Database, generate_id
from services import auth
from services.auth import DeletedProject, Project, ProjectDatabase
from utils.config import ProjectsConfig

_ADMIN_ID = generate_id()
_MEMBER_ID = generate_id()


@pytest.fixture
async def project_db(sql_database_url):
    database = Database(sql_database_url, schemas=auth.SCHEMAS)
    await database.setup()
    yield ProjectDatabase(database, conf=ProjectsConfig(personal_qpu_seconds=60))
    await database.close()


async def test_a_project_and_its_members_round_trip(project_db):
    project = await project_db.create(
        Project(name="p", admin_id=_ADMIN_ID, user_ids=[_ADMIN_ID, _MEMBER_ID])
    )

    assert await project_db.get(project.id) == project
    assert await project_db.get_if_member(project.id, _MEMBER_ID) == project
    assert await project_db.get_if_member(project.id, generate_id()) is None


async def test_projects_are_found_by_member_and_by_fields(project_db):
    first = await project_db.create(
        Project(name="a", admin_id=_ADMIN_ID, user_ids=[_ADMIN_ID], qpu_seconds=5)
    )
    second = await project_db.create(
        Project(name="b", admin_id=_ADMIN_ID, user_ids=[_MEMBER_ID], is_active=False)
    )

    by_member = await project_db.get_many(
        {"$and": [{"name": {"$in": ["a", "b"]}}, {"user_ids": _MEMBER_ID}]}
    )
    active = await project_db.get_many({"is_active": {"$ne": False}})
    funded = await project_db.get_many({"qpu_seconds": {"$gte": 1, "$lte": 10}})

    assert by_member == [second]
    assert active == [first]
    assert funded == [first]


async def test_members_are_added_and_projects_handed_over(project_db):
    project = await project_db.create(
        Project(name="p", admin_id=_ADMIN_ID, user_ids=[_ADMIN_ID])
    )

    await project_db.add_member(project.id, _MEMBER_ID)
    await project_db.add_member(project.id, _MEMBER_ID)
    handed_over = await project_db.set_admin(project.id, _MEMBER_ID)
    charged = await project_db.increment_qpu_seconds(project.id, -2.5)
    renamed = await project_db.update(charged, {"name": "q", "user_ids": [_MEMBER_ID]})

    assert handed_over.admin_id == _MEMBER_ID
    assert handed_over.user_ids == [_ADMIN_ID, _MEMBER_ID]
    assert charged.qpu_seconds == -2.5
    assert (renamed.name, renamed.user_ids) == ("q", [_MEMBER_ID])


async def test_a_deleted_project_is_kept_among_the_deleted(project_db):
    project = await project_db.create(
        Project(name="p", admin_id=_ADMIN_ID, user_ids=[_ADMIN_ID, _MEMBER_ID])
    )

    await project_db.delete(project)

    deleted = await project_db.database.get(DeletedProject, project.id)
    assert await project_db.get(project.id) is None
    assert deleted.user_ids == [_ADMIN_ID, _MEMBER_ID]


async def test_a_personal_project_is_made_once(project_db):
    user = SimpleNamespace(id=_MEMBER_ID, username="ann")

    first = await project_db.create_personal_project_if_not_exist(user)
    second = await project_db.create_personal_project_if_not_exist(user)

    assert first == second
    assert first.qpu_seconds == 60 and first.user_ids == [_MEMBER_ID]
