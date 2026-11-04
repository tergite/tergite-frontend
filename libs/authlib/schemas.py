# This code is part of Tergite
#
# (C) Copyright François Voron 2019 (fastapi-users 14.0.2, MIT licence; see libs/authlib/LICENSE)
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Pydantic bases for the app's user models: how a user is shown, and an OAuth account"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from libs.storage import Id, generate_id


class BaseUser(BaseModel):
    """A user as shown to clients"""

    model_config = ConfigDict(from_attributes=True)

    id: Id
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False


class BaseOAuthAccount(BaseModel):
    """An OAuth account a user signs in with, as the user's oauth_accounts keep it"""

    model_config = ConfigDict(from_attributes=True)

    id: Id = Field(default_factory=generate_id)
    oauth_name: str
    access_token: str
    expires_at: Optional[int] = None
    refresh_token: Optional[str] = None
    account_id: str
    account_email: str
