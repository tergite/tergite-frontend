# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Data Transfer Objects for the quantum jobs service"""

import enum
from datetime import datetime
from typing import (
    List,
    Literal,
    Optional,
    Self,
    Tuple,
    TypeAlias,
    TypedDict,
    Union,
)

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer

from libs.storage import Id, Schema, StorageSpec
from utils.crypto import get_uuid4_str
from utils.date_time import datetime_to_zulu, get_current_timestamp
from utils.models import create_partial_model

IQPoint: TypeAlias = Tuple[float, float]  # [re, im]  (len = 2)
IQMemory: TypeAlias = List[List[List[IQPoint]]]  # exp -> shot -> IQ points
HexMemory: TypeAlias = List[List[str]]  # exp -> shot -> str ( channel -> bit)


class CreatedJobResponse(TypedDict):
    """The response when a new job is created"""

    job_id: str
    upload_url: str
    access_token: str


class TimestampPair(BaseModel):
    """When a stage of the job started and finished"""

    started: Optional[datetime] = None
    finished: Optional[datetime] = None

    @field_serializer("started", when_used="json")
    def serialize_started(self, value: Optional[datetime]):
        """Convert started to builtin types like str when working with JSON

        Args:
            value: when the stage started
        """
        try:
            return datetime_to_zulu(value)
        except AttributeError:
            return value

    @field_serializer("finished", when_used="json")
    def serialize_finished(self, value: Optional[datetime]):
        """Convert finished to builtin types like str when working with JSON

        Args:
            value: when the stage finished
        """
        try:
            return datetime_to_zulu(value)
        except AttributeError:
            return value


class JobTimestamps(BaseModel):
    """Timestamps for the job"""

    registration: Optional[TimestampPair] = None
    pre_processing: Optional[TimestampPair] = None
    execution: Optional[TimestampPair] = None
    post_processing: Optional[TimestampPair] = None
    final: Optional[TimestampPair] = None

    @property
    def resource_usage(self) -> Optional[float]:
        """the resource usage obtained from this timestamp"""
        try:
            return (self.execution.finished - self.execution.started).total_seconds()
        except (TypeError, AttributeError):
            """
            TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'
            TypeError: unsupported operand type(s) for -: 'NoneType' and 'datetime.datetime'
            TypeError: unsupported operand type(s) for -: 'NoneType' and 'NoneType'
            AttributeError: 'NoneType' object has no attribute 'started'
            AttributeError: 'NoneType' object has no attribute 'finished'
            """
            return None


class JobStatus(str, enum.Enum):
    """The status of a job"""

    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    EXECUTING = "executing"
    CANCELLED = "cancelled"


class JobCreate(BaseModel):
    """The schema used when creating a job"""

    device: str
    calibration_date: str


class JobResultCircuit(BaseModel):
    """What a job's result needs of one of its circuits"""

    name: str
    num_clbits: int


class JobResult(BaseModel):
    """The results of the job"""

    model_config = ConfigDict(
        extra="allow",
    )

    memory: Union[HexMemory, IQMemory] = []
    # how the job ran, which the backend sends with its memory, so that a client can read
    # the memory back without the job's payload; none from an older backend
    shots: Optional[int] = None
    meas_level: Optional[Literal[1, 2]] = None
    meas_return: Optional[Literal["single", "avg"]] = None
    circuits: Optional[List[JobResultCircuit]] = None


class Job(Schema, JobCreate):
    """the job schema"""

    __storage__ = StorageSpec(
        table="jobs", key="job_id", indexes=("job_id",), should_skip_invalid=True
    )
    model_config = ConfigDict(
        extra="allow",
    )

    # never stored nor sent: a job is known by its job_id
    id: Optional[Id] = Field(default=None, exclude=True)
    job_id: str = Field(default_factory=get_uuid4_str)
    project_id: Optional[Id] = None
    user_id: Optional[Id] = None
    status: JobStatus = JobStatus.PENDING
    failure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    timestamps: Optional[JobTimestamps] = None
    download_url: Optional[str] = None
    result: Optional[JobResult] = None
    estimated_duration: Optional[float] = None
    actual_duration: Optional[float] = None
    # encrypted JWT token for use to get logfiles from BCC, and submit job to BCC
    access_token: Optional[str] = None
    created_at: Optional[str] = Field(default_factory=get_current_timestamp)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)

    @computed_field
    @property
    def duration_in_secs(self) -> Optional[float]:
        """Duration of execution of the job"""
        try:
            return self.timestamps.resource_usage
        except AttributeError:
            return None


class JobStatusResponse(BaseModel):
    """The response returned when getting the status of the job"""

    status: JobStatus

    @classmethod
    def from_job(cls, job: Job) -> Self:
        """Extracts the job status response from the job

        Args:
            job: the job

        Returns:
            the job's status response
        """
        return cls(status=job.status)


JobQuery = create_partial_model("JobQuery", original=Job, default=Query(None))
JobUpdate = create_partial_model(
    "JobUpdate", original=Job, exclude=("duration_in_secs",)
)
