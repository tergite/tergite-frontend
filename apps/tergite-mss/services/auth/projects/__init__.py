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
from typing import Optional, Sequence

from fastapi import APIRouter, Depends
from fastapi_users.authentication import BearerTransport
from pymongo.errors import DuplicateKeyError

import settings

from ..app_tokens.auth_backend import AppTokenAuthenticationBackend
from ..app_tokens.authenticator import AppTokenAuthenticator
from ..app_tokens.database import AppTokenDatabase
from ..app_tokens.routers import get_app_tokens_router
from ..app_tokens.strategy import AppTokenStrategy
from ..users import get_user_db
from ..users.database import UserDatabase
from ..users.dtos import CurrentUserDependency, User
from ..users.manager import UserManagerDependency
from . import routers
from .database import ProjectDatabase
from .dtos import (
    Project,
    ProjectAdminView,
    ProjectCreate,
    ProjectRead,
    ProjectSource,
    ProjectUpdate,
    personal_project_ext_id,
    personal_project_name,
)
from .manager import ProjectAppTokenManager, ProjectManagerDependency
from .routers import CurrentSuperUserDependency, CurrentUserIdDependency


async def get_project_db():
    """Dependency injector of the projects database"""
    yield ProjectDatabase()


async def ensure_personal_project(user: User) -> Optional[Project]:
    """Creates the user's personal project if they do not have one yet.

    Idempotent, and safe against concurrent logins: ext_id is derived from the user ID
    so the unique index on ext_id rejects the loser of a race, which is then re-read.

    Args:
        user: the user whose personal project is required

    Returns:
        the personal project, or None if personal projects are disabled
    """
    if not settings.CONFIG.projects.personal_projects_enabled:
        return None

    ext_id = personal_project_ext_id(user.id)
    existing = await ProjectDatabase.get_by_ext_id(ext_id)
    if existing is not None:
        return existing

    project = Project(
        ext_id=ext_id,
        name=personal_project_name(user.email),
        qpu_seconds=settings.CONFIG.projects.personal_qpu_seconds,
        admin_id=str(user.id),
        user_ids=[str(user.id)],
        user_emails=[user.email],
        admin_email=user.email,
        is_personal=True,
        source=ProjectSource.INTERNAL,
    )
    try:
        await project.create()
    except DuplicateKeyError:
        return await ProjectDatabase.get_by_ext_id(ext_id)

    return project


def get_app_token_backend(
    app_token_generation_url: str,
) -> AppTokenAuthenticationBackend:
    """Creates an auth backend that uses database app tokens to authenticate"""
    bearer_transport = BearerTransport(tokenUrl=app_token_generation_url)

    def get_app_token_strategy(
        token_db: AppTokenDatabase = Depends(get_app_token_db),
    ) -> AppTokenStrategy:
        return AppTokenStrategy(token_db)

    return AppTokenAuthenticationBackend(
        name="app-token",
        transport=bearer_transport,
        get_strategy=get_app_token_strategy,
    )


async def get_app_token_db():
    """Dependency injector for getting app token database"""
    yield AppTokenDatabase()


async def get_project_manager(
    project_db: ProjectDatabase = Depends(get_project_db),
    app_token_db: AppTokenDatabase = Depends(get_app_token_db),
    user_db: UserDatabase = Depends(get_user_db),
):
    """Dependency injector for ProjectAppTokenManager"""
    yield ProjectAppTokenManager(project_db, app_token_db=app_token_db, user_db=user_db)


class ProjectBasedAuth:
    def __init__(
        self,
        get_project_manager_dep: ProjectManagerDependency,
        get_user_manager_dep: UserManagerDependency,
        get_current_user_dep: CurrentUserDependency,
        get_current_user_id_dep: CurrentUserIdDependency,
        get_current_superuser_dep: CurrentSuperUserDependency,
        auth_backends: Sequence[AppTokenAuthenticationBackend],
    ):
        self.authenticator = AppTokenAuthenticator(
            backends=auth_backends, get_project_manager_dep=get_project_manager_dep
        )
        self.get_project_manager = get_project_manager_dep
        self.get_user_manager = get_user_manager_dep
        self.get_current_user = get_current_user_dep
        self.get_current_user_id = get_current_user_id_dep
        self.get_current_superuser = get_current_superuser_dep
        self.current_project = self.authenticator.current_project
        self.current_project_and_user_ids = (
            self.authenticator.current_project_and_user_ids
        )

    def get_app_tokens_router(
        self, backend: AppTokenAuthenticationBackend
    ) -> APIRouter:
        """
        Return an auth router for a given authentication backend.

        Args:
            backend: The authentication backend instance.
        """
        return get_app_tokens_router(
            backend=backend,
            get_project_manager=self.get_project_manager,
            get_user_manager=self.get_user_manager,
            get_current_user_id=self.get_current_user_id,
        )

    def get_projects_router(self) -> APIRouter:
        """Return a router with routes to manage projects"""
        return routers.get_projects_router(
            get_project_manager=self.get_project_manager,
            get_current_superuser=self.get_current_superuser,
            project_update_schema=ProjectUpdate,
            project_create_schema=ProjectCreate,
        )

    def get_my_projects_router(self) -> APIRouter:
        """Return a router for viewing current user's projects."""
        return routers.get_my_projects_router(
            get_project_manager=self.get_project_manager,
            get_user_manager=self.get_user_manager,
            get_current_user_id=self.get_current_user_id,
            project_schema=ProjectRead,
        )
