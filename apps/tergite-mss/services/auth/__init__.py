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

from .app_tokens import ProjectBasedAuth, get_app_token_backend
from .app_tokens.dtos import (
    AppToken,
    AppTokenCreate,
    AppTokenListResponse,
    AppTokenQuery,
    AppTokenRead,
    AppTokenUpdate,
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
from .service import get_user_emails, on_startup, register_oauth2_client
from .users import (
    UserBasedAuth,
    UserDatabase,
    get_email_validator,
    get_jwt_cookie_backend,
    get_jwt_header_backend,
    get_user_db,
)
from .users.dtos import User, UserCreate, UserRead, UserUpdate
from .users.exc import UnsupportedOauthException
from .users.manager import UserManager
from .users.validators import Validator

SCHEMAS = (AppToken, Project, DeletedProject)

__all__ = [
    "SCHEMAS",
    "UserRead",
    "UserCreate",
    "UserUpdate",
    "User",
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
    "UserDatabase",
    "AppToken",
    "AppTokenRead",
    "AppTokenCreate",
    "AppTokenListResponse",
    "AuthProvider",
    "service",
    "on_startup",
    "get_user_emails",
    "UnsupportedOauthException",
    "ProjectBasedAuth",
    "UserBasedAuth",
    "get_app_token_backend",
    "get_jwt_cookie_backend",
    "get_jwt_header_backend",
    "AppTokenQuery",
    "AppTokenUpdate",
    "AppTokenNotFound",
    "TokenOwner",
    "create_app_token",
    "delete_app_token",
    "find_app_tokens",
    "get_token_owner",
    "update_app_token_expiry",
    "get_email_validator",
    "Validator",
    "get_user_db",
    "UserManager",
    "register_oauth2_client",
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
