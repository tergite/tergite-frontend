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

"""App token authorization based on projects.

Every app token is attached to a given project and a given user
It has a limited amount of time in which it is to be operational.
"""
from typing import Optional, Sequence

from fastapi_users.authentication import BearerTransport

from libs.storage import Database

from .auth_backend import AppTokenAuthenticationBackend
from .authenticator import AppTokenAuthenticator
from .strategy import AppTokenStrategy

# FIXME: the app tokens' strategy uses this Database until step 5.3 replaces it
#   with access rules on the Database the routes pass
_database: Optional[Database] = None


def on_startup(database: Database) -> None:
    """Sets the database the app tokens' strategy reads tokens from"""
    global _database
    _database = database


def get_app_token_backend(
    app_token_generation_url: str,
) -> AppTokenAuthenticationBackend:
    """Creates an auth backend that uses database app tokens to authenticate"""
    bearer_transport = BearerTransport(tokenUrl=app_token_generation_url)

    def get_app_token_strategy() -> AppTokenStrategy:
        return AppTokenStrategy(_database)

    return AppTokenAuthenticationBackend(
        name="app-token",
        transport=bearer_transport,
        get_strategy=get_app_token_strategy,
    )


class ProjectBasedAuth:
    def __init__(self, auth_backends: Sequence[AppTokenAuthenticationBackend]):
        self.authenticator = AppTokenAuthenticator(backends=auth_backends)
        self.current_project = self.authenticator.current_project
        self.current_project_and_user_ids = (
            self.authenticator.current_project_and_user_ids
        )
        self.get_project_and_user = self.authenticator.get_project_and_user
