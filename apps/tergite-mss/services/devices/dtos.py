# This code is part of Tergite
#
# (C) Copyright Simon Genne, Arvid Holmqvist, Bashar Oumari, Jakob Ristner,
#               Björn Rosengren, and Jakob Wik 2022 (BSc project)
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
#
# Refactored by Martin Ahindura 2023-11-08
from enum import Enum
from typing import (
    TYPE_CHECKING,
    AbstractSet,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Tuple,
    Type,
    Union,
)

from beanie import PydanticObjectId
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic.main import IncEx

from utils.api import GeneralMessage
from utils.models import create_partial_model

from ..calibration.dtos import DeviceCalibrationCreate
from ..jobs.dtos import JobUpdate

if TYPE_CHECKING:
    DictStrAny = Dict[str, Any]
    IntStr = Union[int, str]
    AbstractSetIntStr = AbstractSet[IntStr]
    MappingIntStrAny = Mapping[IntStr, Any]


class DeviceEventName(str, Enum):
    INITIALIZED = "initialized"
    RECALIBRATED = "recalibrated"
    JOB_UPDATED = "job_updated"


class DeviceUpsert(BaseModel):
    """The schema for upserting device"""

    model_config = ConfigDict(extra="allow")

    name: str
    version: str
    number_of_qubits: int
    last_online: Optional[str] = None
    is_online: bool
    basis_gates: List[str]
    coupling_map: List[Tuple[int, int]]
    coordinates: List[Tuple[int, int]]
    is_simulator: bool
    coupling_dict: Dict[str, Union[str, List[str]]]
    characterized: bool
    open_pulse: bool
    meas_map: List[List[int]]
    description: str = None
    number_of_couplers: int = 0
    number_of_resonators: int = 0
    dt: Optional[float] = None
    dtm: Optional[float] = None
    qubit_ids: List[str] = []
    meas_lo_freq: Optional[List[int]] = None
    qubit_lo_freq: Optional[List[int]] = None
    gates: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    qubit_ids_coupler_map: List[Tuple[Tuple[int, int], int]] = []

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
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
        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
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


class Device(DeviceUpsert):
    """The Schema for the devices"""

    model_config = ConfigDict(
        from_attributes=True,
        extra="allow",
    )

    id: PydanticObjectId = Field(alias="_id")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


type DeviceEventData = Union[DeviceUpsert, DeviceCalibrationCreate, JobUpdate]
"""Data type for the data attached to device events"""


class DeviceEventHandler(Protocol):
    """The signature of all event handlers for device events"""

    async def __call__(self, device: str, data: JobUpdate, **kwargs) -> GeneralMessage:
        """Handles the given device event

        Args:
            device: The device where the event occurred
            data: The data associated with the event

        Returns:
            the general message showing the output from the handler
        """


class DeviceEvent(BaseModel):
    """The schema for device events"""

    __status_data_map__: Dict[DeviceEventName, Type[DeviceEventData]] = {
        DeviceEventName.INITIALIZED: DeviceUpsert,
        DeviceEventName.RECALIBRATED: DeviceCalibrationCreate,
        DeviceEventName.JOB_UPDATED: JobUpdate,
    }

    name: DeviceEventName
    data: DeviceEventData

    @field_validator("data", mode="after")
    @classmethod
    def validate_data(
        cls, value: DeviceEventData, info: ValidationInfo
    ) -> DeviceEventData:
        """Validates the data depending on the name type"""
        expected_data_cls = cls.__status_data_map__[info.data["name"]]
        if not isinstance(value, expected_data_cls):
            raise ValueError(
                f"data must be of type {expected_data_cls.__name__}, was {type(value)}"
            )

        return value


# derived models
DeviceQuery = create_partial_model(
    "DeviceQuery",
    original=Device,
    default=Query(None),
    exclude=(
        "basis_gates",
        "coupling_map",
        "coordinates",
        "coupling_dict",
        "meas_map",
        "qubit_ids",
        "meas_lo_freq",
        "qubit_lo_freq",
        "gates",
        "qubit_ids_coupler_map",
    ),
)
