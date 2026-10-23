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

"""The record of a request id or websocket nonce, kept long enough to reject a replay"""
from datetime import datetime
from typing import Optional

from pydantic import Field

from libs.storage import Id, Schema, StorageSpec, generate_id


class RequestLog(Schema):
    __storage__ = StorageSpec(
        table="request_logs", unique=("request_id",), expires="expires_at"
    )

    id: Id = Field(default_factory=generate_id)
    request_id: str
    # the x-id header, which names the device on a BCC websocket
    client_name: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    expires_at: datetime
