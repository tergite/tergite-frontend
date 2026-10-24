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
from utils.api import PaginatedListResponse
from utils.config import Oauth2ClientConfig, UserRole

from .access import LAX, STRICT, SYSTEM, AccessRule, check_project_access
from .app_tokens.dtos import (
    AppToken,
    AppTokenCreate,
    AppTokenListResponse,
    AppTokenQuery,
    AppTokenRead,
    AppTokenUpdate,
    BearerResponse,
    TokenOwner,
)
from .app_tokens.exc import AppTokenNotFound
from .app_tokens.service import (
    create_app_token,
    delete_app_token,
    find_app_tokens,
    get_token_owner,
    update_app_token_expiry,
)
from .projects.dtos import (
    DeletedProject,
    Project,
    ProjectAdminView,
    ProjectCreate,
    ProjectQuery,
    ProjectRead,
    ProjectUpdate,
)
from .projects.exc import ExtendedErrorCode, ProjectExists, ProjectNotExists
from .projects.service import (
    add_member,
    create_project,
    delete_project,
    ensure_personal_project,
    find_projects,
    get_admin_view,
    get_project,
    get_project_if_member,
    increment_qpu_seconds,
    remove_member,
    set_admin,
    update_project,
)
from .providers.dtos import AuthProvider
from .service import ensure_roles, get_user_emails, on_startup
from .users import OAuthAccount, Role, User, UserRead
from .utils import get_oauth2_client

SCHEMAS = (AppToken, Project, DeletedProject, Role, User)

__all__ = [
    "SCHEMAS",
    "UserRead",
    "User",
    "Role",
    "OAuthAccount",
    "ensure_roles",
    "get_oauth2_client",
    "UserRole",
    "Oauth2ClientConfig",
    "Project",
    "DeletedProject",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectRead",
    "ProjectAdminView",
    "ProjectQuery",
    "ProjectExists",
    "ProjectNotExists",
    "ExtendedErrorCode",
    "PaginatedListResponse",
    "AppToken",
    "AppTokenRead",
    "AppTokenCreate",
    "AppTokenListResponse",
    "AuthProvider",
    "service",
    "on_startup",
    "get_user_emails",
    "AccessRule",
    "LAX",
    "STRICT",
    "SYSTEM",
    "check_project_access",
    "AppTokenQuery",
    "AppTokenUpdate",
    "BearerResponse",
    "AppTokenNotFound",
    "TokenOwner",
    "create_app_token",
    "delete_app_token",
    "find_app_tokens",
    "get_token_owner",
    "update_app_token_expiry",
    "add_member",
    "create_project",
    "delete_project",
    "ensure_personal_project",
    "find_projects",
    "get_admin_view",
    "get_project",
    "get_project_if_member",
    "increment_qpu_seconds",
    "remove_member",
    "set_admin",
    "update_project",
]
