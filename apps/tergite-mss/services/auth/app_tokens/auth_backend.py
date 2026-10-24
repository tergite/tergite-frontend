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
"""FastAPIUsers-specific definition of Authentication Backend"""
from fastapi_users.authentication import Transport
from fastapi_users.types import DependencyCallable

from .strategy import AppTokenStrategy


class AppTokenAuthenticationBackend:
    """The transport and strategy app tokens are read with, until step 5.3

    Attributes:
        name: Name of the backend.
        transport: Authentication transport instance.
        get_strategy: Dependency callable returning
            an authentication strategy instance.
    """

    name: str
    transport: Transport

    def __init__(
        self,
        name: str,
        transport: Transport,
        get_strategy: DependencyCallable[AppTokenStrategy],
    ):
        self.name = name
        self.transport = transport
        self.get_strategy = get_strategy
