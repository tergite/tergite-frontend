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
import logging
from typing import Any, Coroutine, TypeVar

import settings

T = TypeVar("T")

# error logger
err_logger = logging.getLogger("uvicorn.error")
# work around for testing to allow errors to be seen in terminal
if settings.CONFIG.environment == "test":
    err_logger.error = print
    err_logger.info = print
    err_logger.warning = print
    err_logger.debug = print


async def log_if_err(
    coro: Coroutine[Any, Any, T],
    err_msg_prefix: str = "suppressed error",
) -> Coroutine[Any, Any, T]:
    """Suppresses the error a coroutine might raise and logs it

    Args:
        coro: the coroutine
        err_msg_prefix: the prefix for the error message that is logged

    Returns:
        the result of the coroutine
    """
    try:
        return await coro
    except Exception as exp:
        err_logger.error(f"{err_msg_prefix}: {exp.__class__.__name__}: {exp}")
