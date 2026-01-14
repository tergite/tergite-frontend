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
"""Data Transfer objects for the puhuri external service"""
import enum
from datetime import datetime
from typing import TYPE_CHECKING, AbstractSet, Any, Dict, List, Mapping, Optional, Union

import pymongo
from beanie import Document
from pydantic import BaseModel, field_serializer
from pymongo import IndexModel
from waldur_client import ComponentUsage

from utils.date_time import datetime_to_zulu

if TYPE_CHECKING:
    DictStrAny = Dict[str, Any]
    IntStr = Union[int, str]
    AbstractSetIntStr = AbstractSet[IntStr]
    MappingIntStrAny = Mapping[IntStr, Any]

PUHURI_USAGE_COLLECTION = "puhuri_resource_usages"
INTERNAL_USAGE_COLLECTION = "internal_resource_usages"
REQUEST_FAILURES_COLLECTION = "puhuri_failed_requests"


class PuhuriProjectMetadata(BaseModel):
    """Metadata as extracted from Puhuri resources"""

    uuid: str
    # dict of offering_uuid and limits dict
    limits: Dict[str, Dict[str, float]] = {}
    # dict of offering_uuid and limit_usage dict
    limit_usage: Dict[str, Dict[str, float]] = {}
    resource_uuids: List[str]


class PuhuriFailedRequest(Document, extra="allow"):
    """Schema for requests that fail when made to Puhuri"""

    reason: str
    method: str
    payload: Optional[Dict]
    created_on: datetime

    @field_serializer("created_on", when_used="json")
    def serialize_created_on(self, created_on: datetime):
        """Convert created_on to string when working with JSON"""
        return datetime_to_zulu(created_on)


class PuhuriResource(BaseModel, extra="allow"):
    """The schema of the items got from querying api/marketplace-resources"""

    uuid: str
    project_uuid: str
    customer_uuid: str
    offering_uuid: str
    plan_uuid: str
    plan_unit: str  # month, hour, day, half_month
    state: str  # Creating, ...
    is_usage_based: bool  # Here, billing is done after usage...i.e. post paid as opposed to pre-payment o
    # or pre-allocation...which QAL9000 expects
    is_limit_based: bool  # (FIXME: We probably should allow only limit-based resources)
    limits: dict  # e.g. {"pre-paid": 20). the "pre-paid" name is something one has to set in the UI. It can be anything
    # but it is the maximum amount bought by the user

    @property
    def has_limits(self) -> bool:
        """Whether resource has limits or not"""
        return len(self.limits) != 0


class PuhuriOrder(BaseModel, extra="allow"):
    """The schema of the Order objects as got from Puhuri"""

    uuid: str
    project_name: str
    project_description: str
    project_uuid: str
    customer_name: str
    customer_description: str
    items: List["OrderItem"]


class OrderType(str, enum.Enum):
    CREATE = "Create"
    TERMINATE = "Terminate"


class OrderItem(BaseModel, extra="allow"):
    """The schema for the order item of the Puhuri Order"""

    uuid: str
    attributes: dict
    type: OrderType


class PuhuriProviderOffering(BaseModel, extra="allow"):
    """The schema for the provider offerings got from Puhuri"""

    uuid: str
    name: str
    plans: List["PuhuriPlan"]
    components: List["PuhuriComponent"]


class InternalJobResourceUsage(Document):
    job_id: str
    project_id: str
    created_on: datetime
    qpu_seconds: float
    is_processed: bool = False

    class Settings:
        name = INTERNAL_USAGE_COLLECTION
        indexes = [
            IndexModel("job_id", unique=True),
        ]


class PuhuriJobResourceUsage(Document):
    job_id: str
    created_on: datetime
    qpu_seconds: float
    month: int
    year: int
    plan_period_uuid: str = None
    component_type: str = None
    component_amount: float = None

    class Settings:
        name = PUHURI_USAGE_COLLECTION
        indexes = [
            IndexModel("job_id", unique=True),
            IndexModel(
                [
                    ("plan_period_uuid", pymongo.ASCENDING),
                    ("component_type", pymongo.ASCENDING),
                    ("year", pymongo.DESCENDING),
                    ("month", pymongo.DESCENDING),
                ],
            ),
        ]

    @property
    def component_usage(self) -> ComponentUsage:
        """The Waldur/Puhuri component usage for job resource usage instance"""
        return ComponentUsage(
            type=self.component_type,
            # ComponentUsage has 'amount' as int right now, yet the API expects a
            # float of 2 decimal places. Ignore squiggly line
            amount=self.component_amount,
            description=f"{self.qpu_seconds} QPU seconds",
        )


class PuhuriPlanType(str, enum.Enum):
    USAGE_BASED = "usage-based"
    LIMIT_BASED = "limit-based"


class PuhuriComponentUnit(str, enum.Enum):
    # FIXME: We are making a big assumption that when creating components in the puhuri UI, the 'measurement unit's
    #   set on the component are of the following possible values:
    #   'second', 'hour', 'minute', 'day', 'week', 'half_month', and 'month'.
    MONTH = "month"
    HALF_MONTH = "half_month"
    WEEK = "week"
    DAY = "day"
    HOUR = "hour"
    MINUTE = "minute"
    SECOND = "second"

    def to_seconds(self):
        """component unit in terms of seconds"""
        return _COMPONENT_UNIT_SECONDS_MAP[self]

    def from_seconds(self, amount: float) -> float:
        """Get amount from seconds into this given unit, to 2 decimal places

        Args:
            amount: the amount in seconds

        Returns:
            the amount in the current units
        """
        # NOTE: Note The behavior of round() for floats can be surprising: for example, round(2.675, 2) gives 2.67
        #  instead of the expected 2.68. This is not a bug: it’s a result of the fact that most decimal fractions
        #  can’t be represented exactly as a float.
        # See: https://docs.python.org/2/library/functions.html#round
        # For our case, small rounding errors are not so critical.
        return round(amount / _COMPONENT_UNIT_SECONDS_MAP[self], 2)


class PuhuriComponent(BaseModel, extra="allow"):
    """The schema for accounting components"""

    uuid: str
    type: str
    name: str
    measured_unit: PuhuriComponentUnit


class PuhuriPlan(BaseModel, extra="allow"):
    """The schema for the plans for each offering as got from Puhuri"""

    uuid: str
    name: str
    plan_type: PuhuriPlanType
    is_active: bool
    unit: str
    unit_price: str  # float-like str


class PuhuriComponentUsage(BaseModel, extra="allow"):
    """The schema for the component usage as stored within puhuri"""

    uuid: str
    description: str
    type: str
    name: str
    measured_unit: PuhuriComponentUnit
    usage: float


class PuhuriPlanPeriod(BaseModel, extra="allow"):
    """The schema for the plan periods of resources in Puhuri

    Every resource that is in state "OK", has at least one
    plan period.

    There is one plan period per month for each resource.
    """

    uuid: str
    plan_name: str
    start: datetime
    end: Optional[datetime]
    components: List[PuhuriComponentUsage] = []


_COMPONENT_UNIT_SECONDS_MAP: Dict[PuhuriComponentUnit, int] = {
    PuhuriComponentUnit.MONTH: 30 * 24 * 3_600,
    PuhuriComponentUnit.HALF_MONTH: 15 * 24 * 3_600,
    PuhuriComponentUnit.WEEK: 7 * 24 * 3_600,
    PuhuriComponentUnit.DAY: 24 * 3600,
    PuhuriComponentUnit.HOUR: 3_600,
    PuhuriComponentUnit.MINUTE: 60,
    PuhuriComponentUnit.SECOND: 1,
}
