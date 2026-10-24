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
from typing import Callable, Generic, Optional, cast

import pytest
from fastapi import Response

from libs.authlib import models
from libs.authlib.authentication import (
    AuthenticationBackend,
    BearerTransport,
    Strategy,
)
from libs.authlib.authentication.strategy import StrategyDestroyNotSupportedError
from libs.authlib.authentication.transport.base import Transport
from libs.authlib.manager import BaseUserManager
from tests.libs.authlib.conftest import MockStrategy, MockTransport, UserModel


class MockTransportLogoutNotSupported(BearerTransport):
    pass


class MockStrategyDestroyNotSupported(Strategy, Generic[models.UP]):
    async def read_token(
        self, token: Optional[str], user_manager: BaseUserManager[models.UP, models.ID]
    ) -> Optional[models.UP]:
        return None

    async def write_token(self, user: models.UP) -> str:
        return "TOKEN"

    async def destroy_token(self, token: str, user: models.UP) -> None:
        raise StrategyDestroyNotSupportedError


@pytest.fixture(params=[MockTransport, MockTransportLogoutNotSupported])
def transport(request) -> Transport:
    transport_class: type[BearerTransport] = request.param
    return transport_class(tokenUrl="/login")


@pytest.fixture(params=[MockStrategy, MockStrategyDestroyNotSupported])
def get_strategy(request) -> Callable[..., Strategy]:
    strategy_class: type[Strategy] = request.param
    return lambda: strategy_class()


@pytest.fixture
def backend(
    transport: Transport, get_strategy: Callable[..., Strategy]
) -> AuthenticationBackend:
    return AuthenticationBackend(
        name="mock", transport=transport, get_strategy=get_strategy
    )


@pytest.mark.asyncio
@pytest.mark.authentication
async def test_logout(backend: AuthenticationBackend, user: UserModel):
    strategy = cast(Strategy, backend.get_strategy())
    result = await backend.logout(strategy, user, "TOKEN")
    assert isinstance(result, Response)
