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
"""Collection of key-word args for the FastAPI app"""

from contextlib import asynccontextmanager
from functools import partial
from typing import Any, Dict

from fastapi import FastAPI
from loguru import logger

import settings
from libs.storage import Database
from services import jobs as jobs_service
from services import notices
from services.auth import service as auth_service
from services.external import bcc
from services.external.email import Emailer
from utils.config import NoticesConfig
from utils.crypto import load_private_key

from .database import close_database, open_database
from .routers.devices import ws_manager as devices_ws_manager


def get_app_kwargs() -> Dict[str, Any]:
    """Retrieve the key-word args for the app instance

    Returns:
        the FastAPI constructor's key-word args; no API docs outside development
    """
    kwargs = dict(
        title="Main Service Server",
        description="A frontend to all our quantum backends",
        version="2026.11.0-rc.5",
        lifespan=lifespan,
    )

    if settings.CONFIG.environment.lower() != "development":
        kwargs["docs_url"] = None
        kwargs["redoc_url"] = None
        kwargs["openapi_url"] = None

    return kwargs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts the app's database, clients and services, and shuts them down on exit

    Args:
        app: the FastAPI app being served
    """
    logger.info("Initializing Tergite MSS database connections and client services...")
    email_conf = settings.CONFIG.email
    emailer = Emailer(config=email_conf) if email_conf is not None else None
    private_key = load_private_key(
        settings.PRIVATE_KEY_FILE, password=settings.CONFIG.private_key_password
    )
    await bcc.create_clients(settings.CONFIG.backends, private_key=private_key)
    database = await open_database(app, settings.CONFIG.database)
    devices_ws_manager.start_refreshing(database)
    await auth_service.on_startup(database, conf=settings.CONFIG.auth)
    await jobs_service.on_startup(
        private_key=private_key,
        qpu_seconds_low_threshold=settings.CONFIG.projects.qpu_seconds_low_threshold,
    )
    await notices.on_startup(
        database, conf=settings.CONFIG.notices, is_email_enabled=emailer is not None
    )
    if emailer is not None:
        _start_notice_emails(emailer, database, conf=settings.CONFIG.notices)
    logger.info("Tergite MSS startup sequence completed successfully.")

    yield
    logger.info(
        "Tergite MSS shutting down. Closing active connections and cleaning up..."
    )
    await bcc.close_clients()
    # each socket's handler forgets its connection; those it cannot, lapse
    await devices_ws_manager.close_all(reason="server shutting down")
    if emailer is not None:
        emailer.close()
    await close_database(app)
    logger.info("Tergite MSS shutdown sequence completed.")


def _start_notice_emails(
    emailer: Emailer, database: Database, conf: NoticesConfig
) -> None:
    """Starts the emailer on the notices' pending emails"""
    emailer.start(
        interval=conf.email_sweep_interval,
        batch_generator=notices.get_pending_email_batches(
            database,
            batch_size=50,
            dashboard_url=conf.dashboard_url,
            app_name=conf.app_name,
            max_attempts=conf.email_retry_limit,
        ),
        batch_callback=partial(notices.process_email_batch_results, database),
    )
