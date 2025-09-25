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
"""FastAPIUsers-specific definition of Authenticator for app tokens"""
import dataclasses
from inspect import Parameter, Signature
from typing import Callable, List, Optional, Sequence, Tuple, cast

from fastapi import Depends, HTTPException, status
from fastapi_users.authentication import AuthenticationBackend
from fastapi_users.authentication.authenticator import (
    DuplicateBackendNamesError,
    name_to_strategy_variable_name,
    name_to_variable_name,
)
from makefun import with_signature

import settings
from utils.config import UserRole

from ..projects.dtos import Project
from ..projects.manager import ProjectAppTokenManager, ProjectManagerDependency
from ..users.dtos import User
from .auth_backend import AppTokenAuthenticationBackend
from .strategy import AppTokenStrategy


class AppTokenAuthenticator:
    """
    Provides dependency callables to retrieve authenticated project.

    It performs the authentication against a list of backends
    defined by the end-developer. The first backend yielding a user wins.
    If no backend yields a user, an HTTPException is raised.

    Attributes:
        backends: List of authentication backends.
        get_project_manager: Project manager dependency callable.
    """

    backends: Sequence[AppTokenAuthenticationBackend]

    def __init__(
        self,
        backends: Sequence[AppTokenAuthenticationBackend],
        get_project_manager_dep: ProjectManagerDependency,
    ):
        self.backends = backends
        self.get_project_manager = get_project_manager_dep

    def current_project(
        self,
        active: bool = False,
        ignore_qpu_seconds: bool = False,
        user_roles: Tuple[UserRole] = (),
        **kwargs,
    ):
        """Return a dependency callable to retrieve current project.

        Args:
            active: If `True`, throw `401 Unauthorized` if
                the project is inactive. Defaults to `False`.
            ignore_qpu_seconds: If `True`, authorization will succeed even when QPU
                seconds of project are below zero. Defaults to `False`.
            user_roles: Tuple of possible roles the user should have. The user can have any of
                the roles. If the user doesn't have any, a 403 error is raised.
        """
        signature = self._get_dependency_signature()

        @with_signature(signature)
        async def current_project_dependency(*args, **options):
            auth_metadata = await self._authenticate(
                *args,
                active=active,
                ignore_qpu_seconds=ignore_qpu_seconds,
                user_roles=user_roles,
                **options,
            )

            return auth_metadata.project

        return current_project_dependency

    def current_project_and_user_ids(
        self,
        active: bool = False,
        ignore_qpu_seconds: bool = False,
        user_roles: Tuple[UserRole] = (),
        **kwargs,
    ):
        """Return a dependency callable to retrieve current project and user ids.

        Args:
            active: If `True`, throw `401 Unauthorized` if
                the project is inactive. Defaults to `False`.
            ignore_qpu_seconds: If `True`, authorization will succeed even when QPU
                seconds of project are below zero. Defaults to `False`.
            user_roles: Tuple of possible roles the user should have. The user can have any of
                the roles. If the user doesn't have any, a 403 error is raised.
        """
        signature = self._get_dependency_signature()

        @with_signature(signature)
        async def current_project_and_user_id_dependency(*args, **options):
            """Gets current project and user ids

            Returns:
                tuple of (project_id, user_id)
            """
            auth_metadata = await self._authenticate(
                *args,
                active=active,
                ignore_qpu_seconds=ignore_qpu_seconds,
                user_roles=user_roles,
                **options,
            )
            project_id: Optional[str] = (
                None if auth_metadata.project is None else str(auth_metadata.project.id)
            )
            user_id: Optional[str] = (
                None if auth_metadata.user is None else str(auth_metadata.user.id)
            )

            return project_id, user_id

        return current_project_and_user_id_dependency

    async def _authenticate(
        self,
        *args,
        project_manager: ProjectAppTokenManager,
        active: bool = False,
        ignore_qpu_seconds: bool = False,
        user_roles: Tuple[UserRole] = (),
        **kwargs,
    ) -> "AuthMetadata":
        project_user_pair: Optional[Tuple[Project, User]] = None
        token: Optional[str] = None
        enabled_backends: Sequence[AppTokenAuthenticationBackend] = kwargs.get(
            "enabled_backends", self.backends
        )
        for backend in self.backends:
            if backend in enabled_backends:
                token = kwargs[name_to_variable_name(backend.name)]
                strategy: AppTokenStrategy = kwargs[
                    name_to_strategy_variable_name(backend.name)
                ]
                if token is not None:
                    project_user_pair = await strategy.read_token(
                        token, project_manager
                    )

                    if project_user_pair:
                        break

        status_code = status.HTTP_401_UNAUTHORIZED
        error_msg: Optional[str] = None
        if project_user_pair:
            project, user = project_user_pair
            status_code = status.HTTP_403_FORBIDDEN
            if active and not project.is_active:
                status_code = status.HTTP_401_UNAUTHORIZED
                project_user_pair = None
            elif not ignore_qpu_seconds and project.qpu_seconds <= 0:
                # tokens for projects with no qpu allocation
                # are not allowed except if optional is True
                error_msg = f"{project.qpu_seconds} QPU seconds left on project {project.ext_id}"
                project_user_pair = None
            elif user_roles and not any(role in user.roles for role in user_roles):
                # restrict access to only tokens of users with any of the given roles
                project_user_pair = None
            else:
                return AuthMetadata(project=project, user=user, token=token)

        if not project_user_pair:
            raise HTTPException(status_code=status_code, detail=error_msg)
        return AuthMetadata()

    def _get_dependency_signature(self) -> Signature:
        """Generate a dynamic signature for the current_user dependency.
        ♂️
        Thanks to "makefun", we are able to generate callable
        with a dynamic number of dependencies at runtime.
        This way, each security schemes are detected by the OpenAPI generator.
        """
        try:
            parameters: List[Parameter] = [
                Parameter(
                    name="project_manager",
                    kind=Parameter.POSITIONAL_OR_KEYWORD,
                    default=Depends(self.get_project_manager),
                )
            ]

            for backend in self.backends:
                parameters += [
                    Parameter(
                        name=name_to_variable_name(backend.name),
                        kind=Parameter.POSITIONAL_OR_KEYWORD,
                        default=Depends(cast(Callable, backend.transport.scheme)),
                    ),
                    Parameter(
                        name=name_to_strategy_variable_name(backend.name),
                        kind=Parameter.POSITIONAL_OR_KEYWORD,
                        default=Depends(backend.get_strategy),
                    ),
                ]

            return Signature(parameters)
        except ValueError:
            raise DuplicateBackendNamesError()


@dataclasses.dataclass
class AuthMetadata:
    """Metadata got after authentication"""

    project: Optional[Project] = None
    user: Optional[User] = None
    token: Optional[str] = None
