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
"""The projects service on each database: projects, their members and deletions"""
from types import SimpleNamespace

import pytest

from libs.storage import Database, generate_id
from services import auth
from services.auth import AppToken, DeletedProject, Project, ProjectQuery
from utils.exc import ForbiddenError

_ADMIN_ID = generate_id()
_MEMBER_ID = generate_id()


@pytest.fixture
async def database(database_url):
    database = Database(database_url, schemas=auth.SCHEMAS)
    await database.setup()
    yield database
    await database.close()


async def test_a_project_and_its_members_round_trip(database):
    project = await database.insert(
        Project, Project(name="p", admin_id=_ADMIN_ID, user_ids=[_ADMIN_ID, _MEMBER_ID])
    )

    assert await auth.get_project(database, project.id) == project
    assert await auth.get_project_if_member(database, project.id, _MEMBER_ID) == project
    assert await auth.get_project_if_member(database, project.id, generate_id()) is None
    with pytest.raises(auth.ProjectNotExists):
        await auth.get_project(database, generate_id())


async def test_projects_are_found_by_member_and_by_fields(database):
    first = await database.insert(
        Project, Project(name="a", admin_id=_ADMIN_ID, user_ids=[_ADMIN_ID], qpu_seconds=5)
    )
    second = await database.insert(
        Project,
        Project(name="b", admin_id=_ADMIN_ID, user_ids=[_MEMBER_ID], is_active=False),
    )

    by_member = await auth.find_projects(
        database, ProjectQuery(name=["a", "b"]), member_id=_MEMBER_ID
    )
    active = await auth.find_projects(database, ProjectQuery(is_active=True))
    funded = await auth.find_projects(
        database, ProjectQuery(min_qpu_seconds=1, max_qpu_seconds=10)
    )

    assert by_member == [second]
    assert active == [first]
    assert funded == [first]


async def test_members_are_added_and_projects_handed_over(database):
    project = await database.insert(
        Project, Project(name="p", admin_id=_ADMIN_ID, user_ids=[_ADMIN_ID])
    )

    await auth.add_member(database, project.id, _MEMBER_ID)
    await auth.add_member(database, project.id, _MEMBER_ID)
    handed_over = await auth.set_admin(database, project.id, _MEMBER_ID)
    charged = await auth.increment_qpu_seconds(database, project.id, -2.5)

    assert handed_over.admin_id == _MEMBER_ID
    assert handed_over.user_ids == [_ADMIN_ID, _MEMBER_ID]
    assert charged.qpu_seconds == -2.5


async def test_a_deleted_project_is_kept_with_its_tokens_gone(database):
    project = await database.insert(
        Project, Project(name="p", admin_id=_ADMIN_ID, user_ids=[_ADMIN_ID, _MEMBER_ID])
    )
    await database.insert(
        AppToken,
        AppToken(
            title="t", token="t", user_id=_MEMBER_ID, project_id=project.id, lifespan_seconds=60
        ),
    )

    await auth.delete_project(database, project)

    deleted = await database.get(DeletedProject, project.id)
    assert await database.get(Project, project.id) is None
    assert deleted.user_ids == [_ADMIN_ID, _MEMBER_ID]
    assert await database.count(AppToken) == 0


async def test_a_personal_project_is_made_once_and_kept_from_its_owner(database):
    user = SimpleNamespace(id=_MEMBER_ID, username="ann")

    first = await auth.ensure_personal_project(database, user, qpu_seconds=60)
    second = await auth.ensure_personal_project(database, user, qpu_seconds=60)

    assert first == second
    assert first.qpu_seconds == 60 and first.user_ids == [_MEMBER_ID]
    with pytest.raises(ForbiddenError):
        await auth.delete_project(database, first)
