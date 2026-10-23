# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Utilities for logging"""
import json
import logging
import sys
import traceback
from typing import Collection

from loguru import logger

# error logger wrapper to preserve backward compatibility


UNLOGGED_PATHS = frozenset({"/health"})
"""Paths polled by machines rather than requested by people.

The container healthcheck hits these every few seconds, which buries real traffic in
both the request log and uvicorn's access log.
"""


class EndpointFilter(logging.Filter):
    """Drops uvicorn access-log records for the given paths"""

    def __init__(self, paths: Collection[str]):
        super().__init__()
        self._paths = tuple(paths)

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args or ()
        # uvicorn.access logs (client_addr, method, full_path, http_version, status)
        path = args[2] if len(args) > 2 and isinstance(args[2], str) else None
        if path is None:
            return True
        return not any(path.startswith(item) for item in self._paths)


class InterceptHandler(logging.Handler):
    """Custom logging handler that intercepts standard Python logging logs
    and redirects them to Loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def json_formatter(record):
    """Serialize Loguru records to a single-line flat JSON object."""
    # Handle exception if present
    exception_data = None
    exception = record["exception"]
    if exception is not None:
        exception_data = {
            "type": exception.type.__name__,
            "value": str(exception.value),
            "traceback": "".join(
                traceback.format_exception(
                    exception.type, exception.value, exception.traceback
                )
            ),
        }

    # Construct the flat structured log object
    log_object = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "logger": record["name"],
        "file": f"{record['file'].name}:{record['line']}",
        "function": record["function"],
        "process_id": record["process"].id,
        "thread_id": record["thread"].id,
    }

    # Inject contextual variables from extra (e.g. request_id)
    for key, val in record["extra"].items():
        if key != "request_id_display":
            log_object[key] = val

    # If exception is present, add to json
    if exception_data:
        log_object["exception"] = exception_data

    # Save serialized string to extra and return standard key
    record["extra"]["serialized"] = json.dumps(log_object)
    return "{extra[serialized]}\n"


def patch_record(record):
    """Patch record to ensure request_id exists and formats display correctly."""
    request_id = record["extra"].get("request_id")
    if request_id:
        record["extra"]["request_id_display"] = f"[ID:{request_id}] | "
    else:
        record["extra"]["request_id_display"] = ""


def setup_logging(environment: str):
    """Configure Loguru to handle all logging in the application."""
    # Remove default Loguru handlers
    logger.remove()

    # Determine log level
    log_level = "DEBUG"
    if environment == "production":
        log_level = "INFO"
    elif environment == "test":
        log_level = "WARNING"

    # Configure Loguru based on environment
    if environment == "production":
        # Production: structured JSON logging (single line per record)
        logger.add(
            sys.stdout,
            level=log_level,
            format=json_formatter,
        )
    else:
        # Development / Test: colored, human-readable logging
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "{extra[request_id_display]}"
            "<level>{message}</level>"
        )
        logger.configure(patcher=patch_record)
        logger.add(sys.stderr, level=log_level, format=log_format)

    # Intercept standard library logging records
    std_level = logging.getLevelName(log_level)
    logging.basicConfig(handlers=[InterceptHandler()], level=std_level, force=True)

    # Attach InterceptHandler to key loggers and disable their custom handlers to avoid duplicates
    intercept_loggers = [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "beanie",
        "motor",
    ]
    for logger_name in intercept_loggers:
        std_logger = logging.getLogger(logger_name)
        std_logger.handlers = []
        std_logger.propagate = True

    # a logger's filter runs before propagation, so this drops the record outright
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.filters = [
        item for item in access_logger.filters if not isinstance(item, EndpointFilter)
    ]
    access_logger.addFilter(EndpointFilter(UNLOGGED_PATHS))
