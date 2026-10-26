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

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import settings
from api.errors import (
    handle_bcc_http_error,
    make_exception_group_handler,
    make_http_error_handler,
)
from api.middleware import RequestIDMiddleware
from libs import authlib
from utils.date_time import set_datetime_precision
from utils.exc import (
    BccHttpError,
    ConflictError,
    ForbiddenError,
    InvalidInputError,
    InvalidRequestIDError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    UnknownBccError,
)
from utils.logging import setup_logging

from .app_kwargs import get_app_kwargs
from .dashboard import include_dashboard
from .routers.admin import router as admin_router
from .routers.auth import include_auth_router
from .routers.booking import router as booking_router
from .routers.calibrations import router as calibrations_router
from .routers.counts import router as counts_router
from .routers.devices import router as devices_router
from .routers.jobs import router as jobs_router
from .routers.me import router as my_router

# the dashboard's build, which a checkout lacks until `npm run build` in ui/
DASHBOARD_DIR = Path(__file__).parents[1] / "ui" / "dist"

setup_logging(settings.CONFIG.environment)

set_datetime_precision(settings.CONFIG.datetime_precision)

app = FastAPI(**get_app_kwargs())

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    # credentialed requests need their origin echoed, never '*'
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(NotFoundError, make_http_error_handler(404))
app.add_exception_handler(
    ValueError, make_http_error_handler(500, "Unexpected server error")
)
app.add_exception_handler(
    TypeError, make_http_error_handler(500, "Unexpected server error")
)
app.add_exception_handler(
    RuntimeError, make_http_error_handler(500, "Unexpected server error")
)
app.add_exception_handler(ServiceUnavailableError, make_http_error_handler(503))
app.add_exception_handler(UnknownBccError, make_http_error_handler(400))
app.add_exception_handler(BccHttpError, handle_bcc_http_error)
app.add_exception_handler(InvalidRequestIDError, make_http_error_handler(400))
app.add_exception_handler(InvalidInputError, make_http_error_handler(400))
app.add_exception_handler(UnauthorizedError, make_http_error_handler(401))
app.add_exception_handler(ForbiddenError, make_http_error_handler(403))
app.add_exception_handler(ConflictError, make_http_error_handler(409))
app.add_exception_handler(
    Exception, make_http_error_handler(500, "Unexpected server error")
)
app.add_exception_handler(
    ExceptionGroup, make_exception_group_handler(app.exception_handlers)
)

authlib.add_exception_handlers(app)
include_auth_router(app)
app.include_router(calibrations_router)
app.include_router(devices_router)
app.include_router(my_router)
app.include_router(admin_router)
app.include_router(jobs_router)
app.include_router(booking_router)
app.include_router(counts_router)
if DASHBOARD_DIR.is_dir():
    include_dashboard(app, DASHBOARD_DIR)


@app.get("/health", include_in_schema=False)
async def health():
    """Liveness probe for the container healthcheck.

    Deliberately public, trivial and unlogged: the probe runs every ten seconds and
    drowned the request log when it went through a real endpoint.
    """
    return {"status": "ok"}
