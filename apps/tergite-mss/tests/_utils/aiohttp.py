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
"""Test utils for aiohttp"""
from typing import Any, Dict


class MockAiohttpClient:
    """Mock aiohttp.Client that returns the given text when get is called"""

    def __init__(self, result_map: Dict[str, Any], default: Any = None):
        self._result_map = result_map
        self.default = default

    def get(self, address: str):
        data = self._result_map.get(address, self.default)
        status = 200 if data else 404
        return _MockResponse(status=status, data=data)

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __aenter__(self):
        return self


class _MockResponse:
    def __init__(self, data: Any, status: int):
        self.data = data
        self.status = status

    async def json(self):
        if isinstance(self.data, dict):
            return {**self.data}
        return self.data

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __aenter__(self):
        return self
