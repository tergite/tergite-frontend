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
from functools import cached_property
from typing import (
    Coroutine,
    Dict,
    List,
    Optional,
)

import aiosmtplib
from loguru import logger

from utils.config import EmailConfig

from .dtos import BatchEmailCallback, BatchEmailGenerator, EmailDetails, EmailResult


class Emailer:
    """A process that sends email messages"""

    def __init__(self, config: EmailConfig) -> None:
        if not isinstance(config, EmailConfig):
            raise ValueError("email config needs to be an instance of EmailConfig")

        self._config = config
        smtp_options = config.model_dump(exclude=config.non_smtp_fields)
        self._smtp = aiosmtplib.SMTP(**smtp_options)
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
        batch_generator: BatchEmailGenerator,
        batch_callback: BatchEmailCallback,
        ignore_errors: bool = True,
        **kwargs,
    ):
        """Registers a schedule for sending emails. It must be done before emailer starts.

        Args:
            name: The name of the schedule.
            interval: The interval in seconds between sending emails.
            batch_generator: A generator that yields batch emails to send.
            batch_callback: A callback that will be called on each batch,
                with a sequence of EmailResult in the order of the EmailDetails passed
                where for each index, the EmailResult corresponds to the original EmailDetails
                in that index.
            ignore_errors: Whether to ignore errors during sending.
            **kwargs: Optional arguments for SMTP.send_message().

        Raises:
            ValueError: if the name is already registered.
            RuntimeError: Cannot register a schedule after emailer is started.
        """
        if self._is_started:
            raise RuntimeError("Cannot register a schedule after emailer is started.")
        if name in self.__coroutines:
            raise ValueError(f"Email schedule already registered: {name}")

        self.__coroutines[name] = _send_on_repeat(
            smtp=self._smtp,
            interval=interval,
            from_value=f"{self.from_value}",
            batch_generator=batch_generator,
            batch_callback=batch_callback,
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
        async with self._smtp:
            return await self._smtp.send_message(message, **kwargs)


async def _send_on_repeat(
    smtp: aiosmtplib.SMTP,
    interval: float,
    from_value: str,
    batch_generator: BatchEmailGenerator,
    batch_callback: BatchEmailCallback,
    ignore_errors: bool = True,
    **kwargs,
) -> None:
    """Send email messages on a schedule.

    Args:
        smtp: An aiosmtplib.SMTP instance.
        interval: The interval in seconds between sending emails.
        from_value: Email address field to send from.
        batch_generator: A generator that yields batch of EmailDetail's to send.
        batch_callback: A callback that will be called on each batch,
            with a sequence of EmailResult in the order of the EmailDetails passed
            where for each index, the EmailResult corresponds to the original EmailDetails
            in that index.
        ignore_errors: Whether to ignore errors during sending.
        **kwargs: Optional arguments for SMTP.send_message().

    Raises:
        asyncio.CancelledError: if task is cancelled.
        ValueError: on more than one Resent header block on no sender kwarg or
            From header in message on no recipients kwarg or To, Cc or Bcc header in message
        SMTPRecipientsRefused: delivery to all recipients failed
        SMTPResponseException: on invalid response
    """
    assert interval > 0, "interval must be greater than 0"

    async with aclosing(batch_generator) as email_batches:
        async for batch in email_batches:  # type: Sequence[EmailDetails]
            errors: List[Optional[Exception]] = [None] * len(batch)
            try:
                if batch:
                    async with smtp:
                        for idx, detail in enumerate(batch):
                            try:
                                msg = detail.to_email_message(from_value=from_value)
                                await smtp.send_message(msg, **kwargs)
                            except Exception as exp:
                                if not ignore_errors:
                                    raise
                                logger.exception("sending email on repeat failed")
                                errors[idx] = exp
            except Exception as exp:
                # e.g. connecting to the SMTP server failed, so nothing was sent
                if not ignore_errors:
                    raise
                logger.exception("sending email batch on repeat failed")
                errors = [exp] * len(batch)

            results = [
                EmailResult(
                    error=error, ref_id=detail.ref_id, can_retry=detail.can_retry
                )
                for detail, error in zip(batch, errors)
            ]

            # close processing for current batch, prepare for the next one
            await batch_callback(results)
            await asyncio.sleep(interval)
