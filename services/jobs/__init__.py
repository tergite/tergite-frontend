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
    CreatedJobResponse,
    Job,
    JobCreate,
    JobQuery,
    JobStatus,
    JobStatusResponse,
    JobUpdate,
)
from .service import (
    cancel_job,
    count_job_submitters,
    create_job,
    delete_job,
    get_job,
    get_latest_many,
    get_readable_job,
    on_startup,
    update_job,
    update_qpu_usage,
)

SCHEMAS = (Job,)

__all__ = [
    "SCHEMAS",
    "CreatedJobResponse",
    "Job",
    "JobCreate",
    "JobQuery",
    "JobStatus",
    "JobStatusResponse",
    "JobUpdate",
    "cancel_job",
    "count_job_submitters",
    "create_job",
    "get_latest_many",
    "get_job",
    "get_readable_job",
    "on_startup",
    "delete_job",
    "update_job",
    "update_qpu_usage",
]
