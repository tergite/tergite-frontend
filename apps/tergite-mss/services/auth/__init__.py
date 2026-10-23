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

from .app_tokens.dtos import (
    AppToken,
    AppTokenCreate,
    AppTokenListResponse,
    AppTokenRead,
)
from .projects import (
    ProjectBasedAuth,
    ProjectDatabase,
    get_app_token_backend,
    get_project_db,
    get_project_manager,
)
from .projects.dtos import (
    DeletedProject,
    Project,
    ProjectAdminView,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
from .providers.dtos import AuthProvider
from .service import get_user_emails, on_startup, register_oauth2_client
from .users import (
    UserBasedAuth,
    UserDatabase,
    get_jwt_cookie_backend,
    get_jwt_header_backend,
    get_user_db,
    get_user_manager,
)
from .users.dtos import User, UserCreate, UserRead, UserUpdate
from .users.exc import UnsupportedOauthException

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
    "PaginatedListResponse",
    "ProjectDatabase",
    "UserDatabase",
    "AppToken",
    "AppTokenRead",
    "AppTokenCreate",
    "AppTokenListResponse",
    "AuthProvider",
    "service",
    "on_startup",
    "get_project_db",
    "get_user_emails",
    "UnsupportedOauthException",
    "ProjectBasedAuth",
    "UserBasedAuth",
    "get_app_token_backend",
    "get_jwt_cookie_backend",
    "get_jwt_header_backend",
    "get_project_manager",
    "get_user_db",
    "get_user_manager",
    "register_oauth2_client",
]
