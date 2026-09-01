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
"""The service for sending emails
"""
import asyncio
from contextlib import aclosing
from email.message import EmailMessage
from functools import cached_property
from typing import AsyncGenerator, Coroutine, Dict, Sequence

import aiosmtplib
from loguru import logger
from pydantic import BaseModel

import settings
from utils.config import EmailConfig


class EmailDetails(BaseModel):
    """The details needed to send an email.

    Attributes:
        to: Email address to send.
        subject: Subject of the email.
        body: Body of the email.
    """

    to: str
    subject: str
    body: str

    def to_email_message(self, from_value: str) -> EmailMessage:
        """Converts the details to an email message."""
        message = EmailMessage()
        message["From"] = from_value
        message["To"] = self.to
        message["Subject"] = self.subject
        message.set_content(self.body)
        return message


class Emailer:
    """A process that sends email messages"""

    def __init__(self, config: EmailConfig = settings.CONFIG.email) -> None:
        if not isinstance(config, EmailConfig):
            raise ValueError("email config needs to be an instance of EmailConfig")

        self._config = config
        self._smtp = aiosmtplib.SMTP(
            **config.model_dump(exclude=config._non_smtp_fields)
        )
        self._tasks: Dict[str, asyncio.Task] = {}
        self.__coroutines: Dict[str, Coroutine] = {}
        self._is_started: bool = False

    @cached_property
    def from_value(self):
        """The value to be put in the 'from' email field."""
        return f"{self._config.from_name} <{self._config.from_address}>"

    def start(self) -> None:
        """Starts the emailer and all its schedules.

        No new schedules should be registered after this.
        """
        for name, coro in self.__coroutines.items():
            self._tasks[name] = asyncio.create_task(coro)

        self.__coroutines.clear()
        self._is_started = True
        logger.info("Emailer started.")

    def close(self) -> None:
        """Releases the resources used by the emailer"""
        for task in self._tasks.values():
            task.cancel()

        self._smtp.close()
        self._is_started = False
        self._tasks.clear()
        logger.info("Emailer stopped.")

    def register_batch_schedule(
        self,
        name: str,
        interval: float,
        batch_generator: AsyncGenerator[Sequence[EmailDetails], None],
        ignore_errors: bool = True,
        **kwargs,
    ):
        """Registers a schedule for sending emails. It must be done before emailer starts.

        Args:
            name: The name of the schedule.
            interval: The interval in seconds between sending emails.
            batch_generator: A generator that yields batch emails to send.
            ignore_errors: Whether to ignore errors during sending.
            **kwargs: Optional arguments for SMTP.send_message().

        Raises:
            ValueError: if the name is already registered.
            RuntimeError: Cannot register a schedule after emailer is started.
        """
        if self._is_started:
            raise RuntimeError("Cannot register a schedule after emailer is started.")
        if name in self._tasks:
            raise ValueError(f"Email schedule already registered: {name}")

        self.__coroutines[name] = _send_on_repeat(
            smtp=self._smtp,
            interval=interval,
            from_value=f"{self.from_value}",
            batch_generator=batch_generator,
            ignore_errors=ignore_errors,
            **kwargs,
        )
        logger.info(
            f"Email schedule {name} registered for interval {interval} seconds."
        )

    def get_schedule(self, name: str) -> asyncio.Task:
        """Gets the task that is running the schedule of given name.

        Args:
            name: The name of the schedule.

        Returns:
            The task that is running the schedule.

        Raises:
            KeyError: If the schedule of given name doesn't exist.
        """
        return self._tasks[name]

    async def send(self, details: EmailDetails, **kwargs):
        """Send an email message.

        Args:
            details: EmailDetails to send.
            **kwargs: Optional arguments for SMTP.send_message().

        Raises:
            SMTPRecipientsRefused: delivery to all recipients failed
            SMTPResponseException: on invalid response
            RuntimeError: SMTP client is not configured
        """
        if not self._smtp:
            raise RuntimeError("SMTP client is not configured")

        message = details.to_email_message(from_value=self.from_value)
        logger.debug(f"Sending email to {details.to}: {details.subject}")
        return await self._smtp.send_message(message, **kwargs)


async def _send_on_repeat(
    smtp: aiosmtplib.SMTP,
    interval: float,
    from_value: str,
    batch_generator: AsyncGenerator[Sequence[EmailDetails], None],
    ignore_errors: bool = True,
    **kwargs,
) -> None:
    """Send email messages on a schedule.

    Args:
        smtp: An aiosmtplib.SMTP instance.
        interval: The interval in seconds between sending emails.
        from_value: Email address field to send from.
        batch_generator: A generator that yields batch of EmailDetail's to send.
        ignore_errors: Whether to ignore errors during sending.
        **kwargs: Optional arguments for SMTP.send_message().

    Raises:
        asyncio.CancelledError: if task is cancelled.
    """
    async with aclosing(batch_generator) as email_batches:
        async for batch in email_batches:
            for detail in batch:
                try:
                    msg = detail.to_email_message(from_value=from_value)
                    await smtp.send_message(msg, **kwargs)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    if ignore_errors:
                        logger.exception(f"sending email on repeat failed")
                    else:
                        raise
            # wait for next interval
            await asyncio.sleep(interval)
