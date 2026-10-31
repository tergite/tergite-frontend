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
import dataclasses
from email.message import EmailMessage
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Optional,
    Sequence,
    TypeAlias,
)

from pydantic import BaseModel, computed_field

BatchEmailCallback: TypeAlias = Callable[[Sequence["EmailResult"]], Awaitable[None]]
"""The asynchronous Callback called after every batch of emails is processed

It receives the Sequence of EmailResult, with each corresponding to the EmailDetails
instance that was in the same position in the sequence of EmailDetails that was processed.
"""

BatchEmailGenerator: TypeAlias = AsyncGenerator[Sequence["EmailDetails"], None]
"""The asynchronous generator that yields EmailDetails batches to process"""


@dataclasses.dataclass(frozen=True)
class EmailResult:
    """The result after sending an email"""

    error: Optional[Exception] = None
    ref_id: Any = None
    can_retry: bool = True

    # @computed_field
    @property
    def is_success(self) -> bool:
        return self.error is None


class EmailDetails(BaseModel):
    """The details needed to send an email.

    Attributes:
        to: Email address to send.
        subject: Subject of the email.
        body: Body of the email.
        ref_id: a reference that can be used to track the origin or purpose of the email.
        can_retry: whether this email can be retried.
    """

    to: str
    subject: str
    body: str
    ref_id: Any = None
    can_retry: bool = True

    def to_email_message(self, from_value: str) -> EmailMessage:
        """Converts the details to an email message."""
        message = EmailMessage()
        message["From"] = from_value
        message["To"] = self.to
        message["Subject"] = self.subject
        message.set_content(self.body)
        return message
