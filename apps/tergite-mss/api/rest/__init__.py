# This code is part of Tergite
#
# (C) Copyright Miroslav Dobsicek 2020
# (C) Copyright Simon Genne, Arvid Holmqvist, Bashar Oumari, Jakob Ristner,
#               Björn Rosengren, and Jakob Wik 2022 (BSc project)
# (C) Copyright Fabian Forslund, Niklas Botö 2022
# (C) Copyright Abdullah-Al Amin 2022
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from fastapi import FastAPI
from fastapi.requests import Request
from loguru import logger

import settings
from api.rest.middleware import TergiteCORSMiddleware
from services.auth.utils import TooManyListQueryParams
from utils.api import WebsocketRequestLog, get_request_logs_store, to_http_error
from utils.crypto import get_uuid4_str
from utils.exc import (
    ConflictError,
    DbValidationError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    TooManyRequestsError,
    UnknownBccError,
)
from utils.logging import setup_logging

from . import app_kwargs
from .app_kwargs import get_app_kwargs
from .dependencies import CurrentProjectDep, CurrentStrictProjectDep
from .routers.admin import router as admin_router
from .routers.auth import include_auth_router
from .routers.booking import router as booking_router
from .routers.calibrations import router as calibrations_router
from .routers.counts import router as counts_router
from .routers.devices import router as devices_router
from .routers.jobs import router as jobs_router
from .routers.me import router as my_router
from .utils import get_default_mongodb

# Initialize logging
setup_logging(settings.CONFIG.environment)

# application
app = FastAPI(**get_app_kwargs())


# middleware
app.add_middleware(
    TergiteCORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# probed every few seconds by the container healthcheck; logging them buries real traffic
_UNLOGGED_PATHS = frozenset({"/health"})


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Generates request ID, contextualizes logging, logs requests, and records them in requests_store."""
    import time

    # Resolve request ID (reuse x-request-id header if sent, or generate new)
    request_id = (
        request.headers.get("x-request-id")
        or request.headers.get("X-Request-ID")
        or get_uuid4_str()
    )
    request.state.request_id = request_id

    if request.url.path in _UNLOGGED_PATHS:
        return await call_next(request)

    # Wrap request processing in Loguru context
    with logger.contextualize(request_id=request_id):
        logger.debug(
            f"Incoming request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        start_time = time.time()
        try:
            response = await call_next(request)
            duration = (time.time() - start_time) * 1000

            # Log response based on status code
            log_msg = f"Completed request: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {duration:.2f}ms"
            if response.status_code >= 500:
                logger.error(log_msg)
            elif response.status_code >= 400:
                logger.warning(log_msg)
            else:
                logger.info(log_msg)

        except Exception as exc:
            duration = (time.time() - start_time) * 1000
            logger.exception(
                f"Request crashed: {request.method} {request.url.path} - Duration: {duration:.2f}ms"
            )
            raise exc

        # Handle requests store recording
        requests_store = get_request_logs_store()
        if not requests_store.exists(request_id):
            requests_store.insert(WebsocketRequestLog.from_request(request))

        # Attach request ID to response headers
        response.headers["x-request-id"] = request_id
        response.headers["X-Request-ID"] = request_id
        return response


# exception handlers
app.add_exception_handler(NotFoundError, to_http_error(404))
app.add_exception_handler(ValueError, to_http_error(500, "Unexpected server error"))
app.add_exception_handler(TypeError, to_http_error(500, "Unexpected server error"))
app.add_exception_handler(RuntimeError, to_http_error(500, "Unexpected server error"))
app.add_exception_handler(
    DbValidationError, to_http_error(500, "Unexpected server error")
)
app.add_exception_handler(ServiceUnavailableError, to_http_error(503))
app.add_exception_handler(UnknownBccError, to_http_error(400))
app.add_exception_handler(TooManyListQueryParams, to_http_error(400))
app.add_exception_handler(ForbiddenError, to_http_error(403))
app.add_exception_handler(ConflictError, to_http_error(409))
app.add_exception_handler(TooManyRequestsError, to_http_error(429))
app.add_exception_handler(Exception, to_http_error(500, "Unexpected server error"))

# routes
include_auth_router(app)
app.include_router(calibrations_router)
app.include_router(devices_router)
app.include_router(my_router)
app.include_router(admin_router)
app.include_router(jobs_router)
app.include_router(booking_router)
app.include_router(counts_router)


@app.get("/health", include_in_schema=False)
async def health():
    """Liveness probe for the container healthcheck.

    Deliberately public, trivial and unlogged: the probe runs every ten seconds and
    drowned the request log when it went through a real endpoint.
    """
    return {"status": "ok"}


@app.get("/")
async def home(current_project: CurrentStrictProjectDep):
    return "Welcome to the MSS machine"
