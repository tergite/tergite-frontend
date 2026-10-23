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

from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.types import Message, Send

import settings
from services import request_log
from utils.crypto import get_uuid4_str
from utils.logging import UNLOGGED_PATHS

from .database import get_request_log_database


class TergiteCORSMiddleware(CORSMiddleware):
    """Custom CORS middleware to handle Tergite specific behaviour"""

    async def send(
        self, message: Message, send: Send, request_headers: Headers
    ) -> None:
        if message["type"] != "http.response.start":
            await send(message)
            return

        message.setdefault("headers", [])
        headers = MutableHeaders(scope=message)
        headers.update(self.simple_headers)
        origin = request_headers["Origin"]

        # If all origins are allowed, respond back with the Origin header
        if self.allow_all_origins:
            self.allow_explicit_origin(headers, origin)

        # If we only allow specific origins, then we have to mirror back
        # the Origin header in the response.
        elif not self.allow_all_origins and self.is_allowed_origin(origin=origin):
            self.allow_explicit_origin(headers, origin)

        await send(message)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware for handling all requests IDs in a store"""

    async def dispatch(self, request: Request, call_next):
        """Generates request ID, and records the request IDs in requests_store."""
        if request.url.path in UNLOGGED_PATHS:
            return await call_next(request)

        # Resolve request ID (reuse x-request-id header if sent, or generate new)
        request_id = request.headers.get("x-request-id") or get_uuid4_str()
        request.state.request_id = request_id
        response = await call_next(request)

        await request_log.record_request(
            get_request_log_database(request),
            request_id,
            ttl=settings.CONFIG.request_log_ttl,
            client_name=request.headers.get("x-id"),
            ip_address=request.client.host if request.client else None,
        )

        # Attach request ID to response headers
        response.headers["x-request-id"] = request_id
        return response
