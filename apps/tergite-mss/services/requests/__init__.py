# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from .dtos import (
    Request,
    RequestPostBody,
    RequestRole,
    RequestStatus,
    RequestType,
    RequestUpdate,
)
from .service import (
    ALL_REQ_STATUSES,
    ALL_REQ_TYPES,
    create,
    get_many,
    get_one,
    update,
)

SCHEMAS = (Request,)

__all__ = [
    "SCHEMAS",
    "ALL_REQ_STATUSES",
    "ALL_REQ_TYPES",
    "Request",
    "RequestRole",
    "RequestStatus",
    "RequestType",
    "RequestUpdate",
    "RequestPostBody",
    "create",
    "get_one",
    "get_many",
    "update",
]
