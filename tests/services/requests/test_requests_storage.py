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

import asyncio
from types import SimpleNamespace

import pytest

from libs.storage import Database, generate_id
from services import auth, notices, requests
from services.auth import Project
from services.notices import service as notices_service
from services.requests import (
    Request,
    RequestPostBody,
    RequestStatus,
    RequestType,
    RequestUpdate,
)
from services.requests.dtos import ProjectQpuSecondsMetadata
from utils.config import NoticesConfig
from utils.exc import NotFoundError

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


async def test_a_request_approved_twice_at_once_is_acted_on_once(database, project):
    """An approver clicking twice, or two admins at once, decide the same request"""
    request = await _insert_qpu_seconds_request(database, project, seconds=10)
    approval = RequestUpdate(status=RequestStatus.APPROVED)

    decisions = await asyncio.gather(
        requests.update(database, request.id, approval, current_user=_ADMIN),
        requests.update(database, request.id, approval, current_user=_ADMIN),
        return_exceptions=True,
    )

    project_after = await database.get(Project, project.id)
    assert project_after.qpu_seconds == project.qpu_seconds + 10
    assert sorted(type(decision).__name__ for decision in decisions) == [
        NotFoundError.__name__,
        Request.__name__,
    ]


async def test_a_request_approved_and_rejected_at_once_is_stored_as_acted_on(
    database, project
):
    request = await _insert_qpu_seconds_request(database, project, seconds=10)

    await asyncio.gather(
        requests.update(
            database,
            request.id,
            RequestUpdate(status=RequestStatus.APPROVED),
            current_user=_ADMIN,
        ),
        requests.update(
            database,
            request.id,
            RequestUpdate(status=RequestStatus.REJECTED, rejection_reason="no"),
            current_user=_ADMIN,
        ),
        return_exceptions=True,
    )

    stored = await database.get(Request, request.id)
    project_after = await database.get(Project, project.id)
    is_seconds_added = project_after.qpu_seconds == project.qpu_seconds + 10
    assert (stored.status, is_seconds_added) in (
        (RequestStatus.APPROVED, True),
        (RequestStatus.REJECTED, False),
    )


async def _insert_qpu_seconds_request(
    database: Database, project: Project, seconds: float
) -> Request:
    """A pending request of the project's member for more QPU seconds, awaiting the admin"""
    request = Request(
        resource_id=project.id,
        type=RequestType.PROJECT_QPU_SECONDS,
        reason="more",
        metadata=ProjectQpuSecondsMetadata(seconds=seconds),
        requester_id=_MEMBER.id,
        target_user_ids=[_ADMIN.id],
    )
    return await database.insert(Request, request)
