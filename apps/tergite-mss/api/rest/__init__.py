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

import settings
from api.rest.middleware import RequestIDMiddleware, TergiteCORSMiddleware
from services.auth import UnsupportedOauthException
from utils.api import handle_bcc_http_error, to_http_error, unwrap_exception_group
from utils.exc import (
    BccHttpError,
    ConflictError,
    DatabaseError,
    DbValidationError,
    ForbiddenError,
    InvalidInputError,
    InvalidRequestIDError,
    NotFoundError,
    ServiceUnavailableError,
    TooManyRequestsError,
    UnauthorizedError,
    UnknownBccError,
)
from utils.logging import setup_logging

from . import app_kwargs
from .app_kwargs import get_app_kwargs
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

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    TergiteCORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# exception handlers
app.add_exception_handler(NotFoundError, to_http_error(404))
app.add_exception_handler(ValueError, to_http_error(500, "Unexpected server error"))
app.add_exception_handler(TypeError, to_http_error(500, "Unexpected server error"))
app.add_exception_handler(RuntimeError, to_http_error(500, "Unexpected server error"))
app.add_exception_handler(
    DbValidationError, to_http_error(500, "Unexpected server error")
)
app.add_exception_handler(DatabaseError, to_http_error(500, "Unexpected server error"))
app.add_exception_handler(UnsupportedOauthException, to_http_error(500))
app.add_exception_handler(ServiceUnavailableError, to_http_error(503))
app.add_exception_handler(UnknownBccError, to_http_error(400))
app.add_exception_handler(BccHttpError, handle_bcc_http_error)
app.add_exception_handler(InvalidRequestIDError, to_http_error(400))
app.add_exception_handler(InvalidInputError, to_http_error(400))
app.add_exception_handler(UnauthorizedError, to_http_error(401))
app.add_exception_handler(ForbiddenError, to_http_error(403))
app.add_exception_handler(ConflictError, to_http_error(409))
app.add_exception_handler(TooManyRequestsError, to_http_error(429))
app.add_exception_handler(Exception, to_http_error(500, "Unexpected server error"))
app.add_exception_handler(
    ExceptionGroup, unwrap_exception_group(app.exception_handlers)
)

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
