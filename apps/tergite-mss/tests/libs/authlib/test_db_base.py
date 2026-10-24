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
import uuid

import pytest

from libs.authlib.db import BaseUserDatabase
from tests.libs.authlib.conftest import IDType, OAuthAccountModel, UserModel


@pytest.mark.asyncio
@pytest.mark.db
async def test_not_implemented_methods(
    user: UserModel, oauth_account1: OAuthAccountModel
):
    base_user_db = BaseUserDatabase[UserModel, IDType]()

    with pytest.raises(NotImplementedError):
        await base_user_db.get(uuid.uuid4())

    with pytest.raises(NotImplementedError):
        await base_user_db.get_by_email("lancelot@camelot.bt")

    with pytest.raises(NotImplementedError):
        await base_user_db.get_by_oauth_account("google", "user_oauth1")

    with pytest.raises(NotImplementedError):
        await base_user_db.create({})

    with pytest.raises(NotImplementedError):
        await base_user_db.update(user, {})

    with pytest.raises(NotImplementedError):
        await base_user_db.delete(user)

    with pytest.raises(NotImplementedError):
        await base_user_db.add_oauth_account(user, {})

    with pytest.raises(NotImplementedError):
        await base_user_db.update_oauth_account(user, oauth_account1, {})
