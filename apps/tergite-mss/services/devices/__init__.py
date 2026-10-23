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

from .dtos import Device, DeviceEvent, DeviceQuery, DeviceUpsert
from .events import EVENT_HANDLERS
from .service import (
    build_filter,
    disconnect_all,
    find_devices,
    get_device,
    mark_device_offline,
    mark_device_online,
    patch_device,
    upsert_device,
)

SCHEMAS = (Device,)

__all__ = [
    "SCHEMAS",
    "build_filter",
    "Device",
    "DeviceEvent",
    "DeviceQuery",
    "DeviceUpsert",
    "EVENT_HANDLERS",
    "disconnect_all",
    "find_devices",
    "get_device",
    "mark_device_offline",
    "mark_device_online",
    "patch_device",
    "upsert_device",
]
