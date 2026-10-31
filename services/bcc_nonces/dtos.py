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
"""A nonce of a backend's signed websocket handshake, kept as long as its timestamp is fresh"""
from datetime import datetime

from libs.storage import Schema, StorageSpec


class BccNonce(Schema):
    __storage__ = StorageSpec(
        table="bcc_nonces",
        key="nonce",
        # MongoDB makes a key unique only when told; a replay is refused by it
        unique=("nonce",),
        expires="expires_at",
    )

    nonce: str
    device_name: str
    expires_at: datetime
