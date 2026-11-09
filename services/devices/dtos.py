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
from datetime import datetime, timezone
from enum import Enum
from typing import (
    TYPE_CHECKING,
    AbstractSet,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
)

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from libs.storage import Id, Schema, StorageSpec, generate_id
from services.external.bcc import events as bcc_events
from utils.api import GeneralMessage
from utils.models import create_partial_model

from ..calibration.dtos import DeviceCalibrationCreate, PulseFrameKind
from ..jobs.dtos import JobUpdate

if TYPE_CHECKING:
    DictStrAny = Dict[str, Any]
    IntStr = Union[int, str]
    AbstractSetIntStr = AbstractSet[IntStr]
    MappingIntStrAny = Mapping[IntStr, Any]


class DeviceEventName(str, Enum):
    """The name of an event a device sends over its websocket"""

    INITIALIZED = "initialized"
    RECALIBRATED = "recalibrated"
    JOB_UPDATED = "job_updated"
    SWITCHED_OFF = "switched_off"
    SWITCHED_ON = "switched_on"


class DeviceSwitchData(BaseModel):
    """The data of a device's switched_off or switched_on event"""

    date: datetime


class PulseLimits(BaseModel):
    """What a device's pulse-level jobs may play, as its operators set them; a kind of frame
    that a limit by kind leaves out may not be played at all"""

    max_amplitude: Dict[PulseFrameKind, float] = Field(
        description="the largest |sample| of a waveform, as a fraction of full scale"
    )
    max_frequency_offset: float = Field(
        description="hertz a frame may move from its calibrated frequency"
    )
    max_energy_per_shot: Dict[PulseFrameKind, float] = Field(
        description="the sum of |sample|^2 * dt on one frame in one shot, in full scale^2 s"
    )
    max_energy_per_job: Dict[PulseFrameKind, float] = Field(
        description="the energy on one frame over the job, in full scale^2 s"
    )
    max_pulse_duration: float = Field(
        description="seconds of a circuit's pulse-level blocks in one shot"
    )
    max_samples_per_waveform: int = Field(
        description="the samples of one waveform, as played"
    )
    max_capture_duration: float = Field(description="seconds of one capture")


class DeviceUpsert(BaseModel):
    """The schema for upserting device"""

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
    description: Optional[str] = None
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
    # none for a device that takes no pulse-level jobs
    pulse_limits: Optional[PulseLimits] = None


class Device(Schema, DeviceUpsert):
    """The Schema for the devices"""

    __storage__ = StorageSpec(table="devices", key="name", indexes=("name",))
    model_config = ConfigDict(from_attributes=True)

    id: Id
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DeviceConnection(Schema):
    """A websocket that a process of the device's backend holds open to a process of MSS, until
    it closes, or lapses at expires_at, which the MSS process pushes on while it holds it
    """

    __storage__ = StorageSpec(
        table="device_connections", indexes=("device_name",), expires="expires_at"
    )

    id: Id = Field(default_factory=generate_id)
    device_name: str
    connected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime


class SwitchedOffDevice(Schema):
    """A device switched off, until it is switched on"""

    __storage__ = StorageSpec(table="switched_off_devices", key="name")

    name: str
    switched_off_at: datetime


type DeviceEventData = Union[
    DeviceUpsert, DeviceCalibrationCreate, JobUpdate, DeviceSwitchData
]
"""Data type for the data attached to device events"""


type DeviceEventHandler = Callable[..., Awaitable[GeneralMessage]]
"""An event's handler, called with the device, the event's data and the database"""


# a job's update carries what changed, as an older backend sent it
_SentJobUpdate = create_partial_model("SentJobUpdate", original=bcc_events.Job)
# what each event carries, as the backend's spec declares it, and what MSS keeps of it
_EVENT_DATA_CLASSES: Dict[
    DeviceEventName, Tuple[Type[BaseModel], Type[DeviceEventData]]
] = {
    DeviceEventName.INITIALIZED: (bcc_events.Device, DeviceUpsert),
    DeviceEventName.RECALIBRATED: (
        bcc_events.DeviceCalibration,
        DeviceCalibrationCreate,
    ),
    DeviceEventName.JOB_UPDATED: (_SentJobUpdate, JobUpdate),
    DeviceEventName.SWITCHED_OFF: (bcc_events.DeviceSwitchData, DeviceSwitchData),
    DeviceEventName.SWITCHED_ON: (bcc_events.DeviceSwitchData, DeviceSwitchData),
}


class DeviceEvent(BaseModel):
    """The schema for device events"""

    id: str
    name: DeviceEventName
    data: DeviceEventData

    @field_validator("data", mode="before")
    @classmethod
    def validate_data(cls, value: Any, info: ValidationInfo) -> DeviceEventData:
        """Reads the event's data as the backend's spec declares what the event's name
        carries, dropping what it does not declare, then as what MSS keeps of it

        Args:
            value: the event's data, as the backend sent it
            info: the event's fields validated so far, including its name

        Returns:
            what MSS keeps of the data

        Raises:
            ValueError: the data is not what the event's name carries
        """
        if "name" not in info.data:
            raise ValueError("the event has no valid name")
        sent_cls, kept_cls = _EVENT_DATA_CLASSES[info.data["name"]]
        if isinstance(value, kept_cls):
            return value
        sent = sent_cls.model_validate(value)
        return kept_cls.model_validate(sent.model_dump(mode="json", exclude_unset=True))


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
