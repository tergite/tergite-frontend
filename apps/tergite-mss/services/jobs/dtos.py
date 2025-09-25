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
    Any,
    Callable,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    TypeAlias,
    TypedDict,
    Union,
)

from beanie import PydanticObjectId
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer
from pydantic.main import IncEx

from utils.date_time import datetime_to_zulu, get_current_timestamp
from utils.models import create_partial_model

from .utils import get_uuid4_str

IQPoint: TypeAlias = Tuple[float, float]  # [re, im]  (len = 2)
IQMemory: TypeAlias = List[List[List[IQPoint]]]  # exp -> shot -> IQ points
HexMemory: TypeAlias = List[List[str]]  # exp -> shot -> str ( channel -> bit)


class CreatedJobResponse(TypedDict):
    """The response when a new job is created"""

    job_id: str
    upload_url: str
    access_token: str


class TimestampPair(BaseModel):
    started: Optional[datetime] = None
    finished: Optional[datetime] = None

    @field_serializer("started", when_used="json")
    def serialize_started(self, value: Optional[datetime]):
        """Convert started to builtin types like str when working with JSON"""
        try:
            return datetime_to_zulu(value)
        except AttributeError:
            return value

    @field_serializer("finished", when_used="json")
    def serialize_finished(self, value: Optional[datetime]):
        """Convert finished to builtin types like str when working with JSON"""
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
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    EXECUTING = "executing"
    CANCELLED = "cancelled"


class JobCreate(BaseModel):
    """The schema used when creating a job"""

    device: str
    calibration_date: str


class JobResult(BaseModel):
    """The results of the job"""

    model_config = ConfigDict(
        extra="allow",
    )

    memory: Union[HexMemory, IQMemory] = []


class Job(JobCreate):
    """the job schema"""

    model_config = ConfigDict(
        extra="allow",
    )

    id: Optional[PydanticObjectId] = Field(alias="_id", default=None)
    job_id: str = Field(default_factory=get_uuid4_str)
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    failure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    timestamps: Optional[JobTimestamps] = None
    download_url: Optional[str] = None
    result: Optional[JobResult] = None
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

    @field_serializer("id", when_used="json")
    def serialize_id(self, _id: PydanticObjectId):
        """Convert id to builtin types like str when working with JSON"""
        return str(_id)

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: Set[str] | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        fallback: Callable[[Any], Any] | None = None,
        serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        effective_excluded = {"_id", "id"}
        if isinstance(exclude, set):
            effective_excluded.update(exclude)

        return super().model_dump(
            mode=mode,
            include=include,
            exclude=effective_excluded,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=True,
            round_trip=round_trip,
            warnings=warnings,
            fallback=fallback,
            serialize_as_any=serialize_as_any,
        )


class JobStatusResponse(BaseModel):
    """The response returned when getting the status of the job"""

    status: JobStatus

    @classmethod
    def from_job(cls, job: Job):
        """Extracts the job status response from the job"""
        return cls(status=job.status)


# Derived models
JobQuery = create_partial_model("JobQuery", original=Job, default=Query(None))
JobUpdate = create_partial_model(
    "JobUpdate", original=Job, exclude=("job_id", "duration_in_secs")
)
