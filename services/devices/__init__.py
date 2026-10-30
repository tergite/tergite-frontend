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

from .dtos import (
    Device,
    DeviceConnection,
    DeviceEvent,
    DeviceQuery,
    DeviceUpsert,
    SwitchedOffDevice,
)
from .events import EVENT_HANDLERS
from .service import (
    CONNECTION_REFRESH_SECONDS,
    CONNECTION_TTL_SECONDS,
    add_connection,
    find_devices,
    get_device,
    keep_connections_live,
    patch_device,
    remove_connection,
    switch_off_device,
    switch_on_device,
    sync_online_flags,
    upsert_device,
)

SCHEMAS = (Device, DeviceConnection, SwitchedOffDevice)

__all__ = [
    "SCHEMAS",
    "Device",
    "DeviceConnection",
    "DeviceEvent",
    "DeviceQuery",
    "DeviceUpsert",
    "SwitchedOffDevice",
    "CONNECTION_REFRESH_SECONDS",
    "CONNECTION_TTL_SECONDS",
    "EVENT_HANDLERS",
    "add_connection",
    "find_devices",
    "get_device",
    "patch_device",
    "keep_connections_live",
    "remove_connection",
    "switch_off_device",
    "switch_on_device",
    "sync_online_flags",
    "upsert_device",
]
