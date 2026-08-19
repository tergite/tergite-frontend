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
"""Outbound SMTP client.

Lives under services/external because, like bcc, it talks to a system outside this app.
"""
from email.message import EmailMessage
from typing import Optional

import aiosmtplib
from loguru import logger

import settings
from utils.config import EmailConfig
from utils.exc import ServiceUnavailableError


async def send(
    to_address: str,
    subject: str,
    body: str,
    conf: Optional[EmailConfig] = None,
) -> None:
    """Sends one plain-text message.

    Args:
        to_address: the recipient
        subject: the subject line
        body: the plain-text body
        conf: the SMTP settings; defaults to the app config

    Raises:
        ServiceUnavailableError: the email channel is not configured
        aiosmtplib.SMTPException: the message could not be sent
    """
    conf = conf or settings.CONFIG.email
    if conf is None:
        raise ServiceUnavailableError("the email channel is not configured")

    message = EmailMessage()
    message["From"] = f"{conf.from_name} <{conf.from_address}>"
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    logger.debug(f"Sending email to {to_address}: {subject}")
    await aiosmtplib.send(
        message,
        hostname=conf.host,
        port=conf.port,
        username=conf.username,
        password=conf.password,
        start_tls=conf.use_tls,
        timeout=conf.timeout,
    )


def is_configured() -> bool:
    """Whether the email channel can send at all"""
    return settings.CONFIG.email is not None
