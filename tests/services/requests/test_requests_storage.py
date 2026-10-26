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
"""The requests service on each database: requests found by their targets"""
from types import SimpleNamespace

import pytest

from libs.storage import Database, generate_id
from services import auth, notices, requests
from services.auth import Project
from services.notices import service as notices_service
from services.requests import RequestPostBody, RequestStatus, RequestType, RequestUpdate
from utils.config import NoticesConfig

_ADMIN = SimpleNamespace(id=generate_id(), username="admin", is_superuser=False)
_MEMBER = SimpleNamespace(id=generate_id(), username="ann", is_superuser=False)
_OUTSIDER = SimpleNamespace(id=generate_id(), username="bob", is_superuser=False)


@pytest.fixture
async def database(database_url, monkeypatch):
    schemas = [*auth.SCHEMAS, *notices.SCHEMAS, *requests.SCHEMAS]
    database = Database(database_url, schemas=schemas)
    await database.setup()
    # on_startup sets the service's module state, which the running app shares
    for name in ("_conf", "_is_email_enabled"):
        monkeypatch.setattr(notices_service, name, getattr(notices_service, name))
    await notices_service.on_startup(
        database, conf=NoticesConfig(), is_email_enabled=False
    )
    yield database
    await database.close()


@pytest.fixture
async def project(database):
    project = Project(name="p", admin_id=_ADMIN.id, user_ids=[_ADMIN.id, _MEMBER.id])
    return await database.insert(Project, project)


async def test_an_outsider_asks_the_project_admin_for_access(database, project):
    body = RequestPostBody(
        resource_id=project.id, type=RequestType.PROJECT_ACCESS, reason="let me in"
    )

    created = await requests.create(database, body, requester=_OUTSIDER)

    assert created.target_user_ids == [_ADMIN.id]
    assert await requests.get_one(database, created.id, _ADMIN.id) == created
    assert await requests.get_one(database, created.id, _OUTSIDER.id) == created
    assert await requests.get_many(database, _ADMIN.id, role="approver") == [created]
    assert await requests.get_many(database, _OUTSIDER.id, role="requester") == [
        created
    ]
    assert await requests.get_many(database, _MEMBER.id, role="approver") == []


async def test_the_target_rejects_a_request(database, project):
    body = RequestPostBody(
        resource_id=project.id, type=RequestType.PROJECT_ACCESS, reason="let me in"
    )
    created = await requests.create(database, body, requester=_OUTSIDER)

    rejected = await requests.update(
        database,
        created.id,
        RequestUpdate(status=RequestStatus.REJECTED, rejection_reason="no"),
        current_user=_ADMIN,
    )

    pending = await requests.get_many(
        database, _ADMIN.id, role="approver", statuses=(RequestStatus.PENDING,)
    )
    assert rejected.status == RequestStatus.REJECTED
    assert pending == []
