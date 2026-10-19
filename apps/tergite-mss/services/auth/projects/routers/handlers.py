# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Handlers shared by the projects routers and the services that act on projects"""
from ...users.dtos import User
from ..dtos import Project, ProjectCreate
from ..manager import ProjectAppTokenManager
from .utils import notify_membership_change, prepare_new_project


async def create_project(
    payload: ProjectCreate, project_manager: ProjectAppTokenManager, actor: User
) -> Project:
    """Creates a project and tells its members about it

    Users of any emails that do not exist yet are created.

    Args:
        payload: the project to create
        project_manager: the manager of the projects
        actor: the user creating the project

    Returns:
        the created project

    Raises:
        ProjectExists: a project of the same name exists
    """
    project = await prepare_new_project(payload)
    created_project = await project_manager.create(project)
    await notify_membership_change(None, created_project, actor)
    return created_project
