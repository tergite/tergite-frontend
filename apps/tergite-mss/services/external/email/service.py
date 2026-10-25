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
"""The service for sending emails"""
import asyncio
from contextlib import aclosing
from email.message import EmailMessage
from typing import List, Optional

import aiosmtplib
from loguru import logger

from utils.config import EmailConfig

from .dtos import BatchEmailCallback, BatchEmailGenerator, EmailDetails, EmailResult


class Emailer:
    """Sends the batches of emails a generator yields, on repeat, in a background task"""

    def __init__(self, config: EmailConfig) -> None:
        self._smtp = aiosmtplib.SMTP(
            **config.model_dump(exclude=config.non_smtp_fields)
        )
        self._from_value = f"{config.from_name} <{config.from_address}>"
        self._task: Optional[asyncio.Task] = None

    def start(
        self,
        interval: float,
        batch_generator: BatchEmailGenerator,
        batch_callback: BatchEmailCallback,
    ) -> None:
        """Starts sending a batch every interval seconds

        Args:
            interval: the seconds between batches
            batch_generator: a generator that yields the batches of emails to send
            batch_callback: called after each batch with an EmailResult per email, in the
                order of the batch's EmailDetails
        """
        self._task = asyncio.create_task(
            _send_on_repeat(
                self._smtp,
                interval=interval,
                from_value=self._from_value,
                batch_generator=batch_generator,
                batch_callback=batch_callback,
            )
        )
        logger.info(f"Emailer started, sending every {interval} seconds.")

    def close(self) -> None:
        """Releases the resources used by the emailer"""
        if self._task is not None:
            self._task.cancel()
        self._smtp.close()
        logger.info("Emailer stopped.")


async def _send_on_repeat(
    smtp: aiosmtplib.SMTP,
    interval: float,
    from_value: str,
    batch_generator: BatchEmailGenerator,
    batch_callback: BatchEmailCallback,
) -> None:
    """Sends the batches of emails the generator yields, one every interval seconds

    A failure is logged and reported to batch_callback in the email's EmailResult.

    Raises:
        asyncio.CancelledError: if task is cancelled.
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
                                msg = _get_email_message(detail, from_value=from_value)
                                await smtp.send_message(msg)
                            except Exception as exp:
                                logger.exception("sending email on repeat failed")
                                errors[idx] = exp
            except Exception as exp:
                # e.g. connecting to the SMTP server failed, so nothing was sent
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


def _get_email_message(details: EmailDetails, from_value: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = from_value
    message["To"] = details.to
    message["Subject"] = details.subject
    message.set_content(details.body)
    return message
