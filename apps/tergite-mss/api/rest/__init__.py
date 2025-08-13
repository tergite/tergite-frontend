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

import settings
from api.rest.utils import TergiteCORSMiddleware
from services.auth.utils import TooManyListQueryParams
from services.jobs.utils import get_uuid4_str
from utils.api import to_http_error
from utils.exc import (
    DbValidationError,
    NotFoundError,
    ServiceUnavailableError,
    UnknownBccError,
)

from . import app_kwargs
from .app_kwargs import get_app_kwargs
from .dependencies import (
    CurrentProjectDep,
    CurrentStrictProjectDep,
    get_default_mongodb,
)
from .routers.admin import router as admin_router
from .routers.auth import include_auth_router
from .routers.calibrations import router as calibrations_router
from .routers.devices import router as devices_router
from .routers.jobs import router as jobs_router
from .routers.me import router as my_router

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


@app.middleware("http")
async def add_request_id_header(request: Request, call_next):
    """Adds an `x-request-id` header

    It will get it from `x-mss-request-id` if that is present or generate a new one

    Args:
        request: the current FastAPI request object
        call_next: the callback that calls the next middleware or route handler
    """
    request_id = get_uuid4_str()
    request.state.request_id = request_id
    response = await call_next(request)
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

# routes
include_auth_router(app, is_enabled=settings.CONFIG.auth.is_enabled)
app.include_router(calibrations_router)
app.include_router(devices_router)
app.include_router(my_router)
app.include_router(admin_router)
app.include_router(jobs_router)


@app.get("/")
async def home(current_project: CurrentStrictProjectDep):
    return "Welcome to the MSS machine"
