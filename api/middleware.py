# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2024
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from utils.crypto import get_uuid4_str


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Gives each request an ID, which it signs its calls to BCC with and echoes back"""

    async def dispatch(self, request: Request, call_next):
        # Resolve request ID (reuse x-request-id header if sent, or generate new)
        request_id = request.headers.get("x-request-id") or get_uuid4_str()
        request.state.request_id = request_id
        response = await call_next(request)

        # Attach request ID to response headers
        response.headers["x-request-id"] = request_id
        return response
