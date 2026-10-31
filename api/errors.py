# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Exception handlers that turn errors into HTTP responses"""
from inspect import isawaitable
from typing import Any, Awaitable, Callable, Mapping, Optional, Union

from fastapi import HTTPException, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.requests import Request
from loguru import logger

from utils.exc import BccHttpError


def make_http_error_handler(
    status_code: int, custom_message: Optional[str] = None
) -> Callable[[Request, Exception], Union[Response, Awaitable[Response]]]:
    """Makes an error handler that answers with the given status, logging the error

    Args:
        status_code: the HTTP status code
        custom_message: a message to send instead of the exception's own

    Returns:
        an HTTP exception handler function
    """

    async def handle(request: Request, exp: Exception) -> Response:
        if status_code >= 500:
            logger.exception(f"HTTP Server Error {status_code}: {exp}")
        else:
            logger.warning(f"HTTP Client Error {status_code}: {exp}")
        message = custom_message
        if message is None:
            message = f"{exp}"

        http_exp = HTTPException(status_code, message)
        return await http_exception_handler(request, http_exp)

    return handle


async def handle_bcc_http_error(request: Request, exp: BccHttpError) -> Response:
    """An error handler that answers with the status code and message the BCC gave"""
    return await make_http_error_handler(exp.status_code)(request, exp)


def make_exception_group_handler(
    handlers: Mapping[Any, Callable[[Request, Exception], Any]],
) -> Callable[[Request, ExceptionGroup], Awaitable[Response]]:
    """Makes an error handler that answers an exception group of one error as that error

    A group of several errors is answered as any other unexpected exception.

    Args:
        handlers: the app's exception handlers, which must include one for Exception;
            read when an error is handled, so handlers added later are used

    Returns:
        an exception group handler function
    """

    async def handle(request: Request, exp: ExceptionGroup) -> Response:
        error = exp.exceptions[0] if len(exp.exceptions) == 1 else exp
        error_cls = next(cls for cls in type(error).__mro__ if cls in handlers)
        if error_cls is ExceptionGroup:
            error_cls = Exception

        response = handlers[error_cls](request, error)
        if isawaitable(response):
            response = await response
        return response

    return handle
