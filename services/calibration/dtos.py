# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Data Transfer Objects for calibration"""

import enum
from typing import Any, Dict, List, Optional, Union

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from libs.storage import Id, Schema, StorageSpec, generate_id
from utils.date_time import get_current_timestamp
from utils.models import create_partial_model


class CalibrationUnit(str, enum.Enum):
    """The unit of a calibration value"""

    ns = "ns"
    s = "s"
    us = "us"
    GHz = "GHz"
    MHz = "MHz"
    Hz = "Hz"
    rad = "rad"
    deg = "deg"
    EMPTY = ""


class CalibrationValue(BaseModel):
    """A calibration value"""

    unit: CalibrationUnit
    value: Union[float, str, int]
    date: Optional[str] = None


class QubitCalibration(BaseModel):
    """Schema for the calibration data of the qubit"""

    t1_decoherence: Optional[CalibrationValue] = None
    t2_decoherence: Optional[CalibrationValue] = None
    frequency: Optional[CalibrationValue] = None
    anharmonicity: Optional[CalibrationValue] = None
    readout_assignment_error: Optional[CalibrationValue] = None
    # parameters for x gate
    pi_pulse_amplitude: Optional[CalibrationValue] = None
    pi_pulse_duration: Optional[CalibrationValue] = None
    pi_pulse_motzoi: Optional[CalibrationValue] = None
    pulse_type: Optional[CalibrationValue] = None
    pulse_sigma: Optional[CalibrationValue] = None
    id: Optional[int] = None
    index: Optional[CalibrationValue] = None
    x_position: Optional[CalibrationValue] = None
    y_position: Optional[CalibrationValue] = None
    xy_drive_line: Optional[CalibrationValue] = None
    z_drive_line: Optional[CalibrationValue] = None
    # e.g. q12, which the backend computes from the id
    name: Optional[str] = None


class ResonatorCalibration(BaseModel):
    """Schema for the calibration data of the resonator"""

    acq_delay: Optional[CalibrationValue] = None
    acq_integration_time: Optional[CalibrationValue] = None
    frequency: Optional[CalibrationValue] = None
    pulse_amplitude: Optional[CalibrationValue] = None
    pulse_delay: Optional[CalibrationValue] = None
    pulse_duration: Optional[CalibrationValue] = None
    pulse_type: Optional[CalibrationValue] = None
    id: Optional[int] = None
    index: Optional[CalibrationValue] = None
    x_position: Optional[CalibrationValue] = None
    y_position: Optional[CalibrationValue] = None
    readout_line: Optional[CalibrationValue] = None
    # e.g. q12, which the backend computes from the id
    name: Optional[str] = None


class CouplersCalibration(BaseModel):
    """Schema for the calibration data of the coupler"""

    frequency: Optional[CalibrationValue] = None
    frequency_detuning: Optional[CalibrationValue] = None
    anharmonicity: Optional[CalibrationValue] = None
    coupling_strength_02: Optional[CalibrationValue] = None
    coupling_strength_12: Optional[CalibrationValue] = None
    cz_pulse_amplitude: Optional[CalibrationValue] = None
    cz_pulse_dc_bias: Optional[CalibrationValue] = None
    cz_pulse_phase_offset: Optional[CalibrationValue] = None
    cz_pulse_duration_before: Optional[CalibrationValue] = None
    cz_pulse_duration_rise: Optional[CalibrationValue] = None
    cz_pulse_duration_constant: Optional[CalibrationValue] = None
    control_rz_lambda: Optional[CalibrationValue] = None
    target_rz_lambda: Optional[CalibrationValue] = None
    pulse_type: Optional[CalibrationValue] = None
    id: Optional[int] = None
    # e.g. u1, which the backend computes from the id
    short_name: Optional[str] = None
    # the qubits it couples, e.g. q12_q13
    full_name: Optional[str] = None
    control_qubit: Optional[str] = None
    target_qubit: Optional[str] = None


class PulseFrameKind(str, enum.Enum):
    """What a frame plays on: a qubit's drive or readout line, or a coupler's flux line"""

    DRIVE = "drive"
    READOUT = "readout"
    COUPLER = "coupler"


class PulseFrame(BaseModel):
    """A frame a pulse-level job may play on, at its calibrated frequency"""

    name: str = Field(
        description="as a job names it, e.g. q12_drive or q12_q13_coupler"
    )
    kind: PulseFrameKind
    qubits: List[int] = Field(
        description="the physical qubits it acts on, as a job numbers them, e.g. 0 for $0"
    )
    frequency: float = Field(description="its calibrated frequency in hertz")


class GateDefcal(BaseModel):
    """A gate's calibrated pulses, as an OpenPulse defcal, which a job may override"""

    gate: str = Field(description="e.g. x, sx, cz or measure")
    qubits: List[int] = Field(description="the physical qubits it is calibrated on")
    program: str = Field(description="the defcal, e.g. 'defcal x $0 { ... }'")


class DeviceCalibrationCreate(BaseModel):
    """The model used when creating device calibrations in the API"""

    model_config = ConfigDict(from_attributes=True)

    name: str
    version: str
    qubits: List[QubitCalibration]
    resonators: Optional[List[ResonatorCalibration]] = None
    couplers: Optional[List[CouplersCalibration]] = None
    discriminators: Optional[Dict[str, Any]] = None
    frames: Optional[List[PulseFrame]] = None
    defcals: Optional[List[GateDefcal]] = None
    last_calibrated: Optional[str] = Field(default_factory=get_current_timestamp)


class DeviceCalibration(Schema):
    """Schema for the calibration data of a given device"""

    __storage__ = StorageSpec(table="calibrations", key="name", unique=("name",))
    model_config = ConfigDict(from_attributes=True)

    name: str
    version: str
    qubits: List[QubitCalibration]
    resonators: Optional[List[ResonatorCalibration]] = None
    couplers: Optional[List[CouplersCalibration]] = None
    discriminators: Optional[Dict[str, Any]] = None
    frames: Optional[List[PulseFrame]] = None
    defcals: Optional[List[GateDefcal]] = None
    last_calibrated: Optional[str] = Field(default_factory=get_current_timestamp)
    id: Id = Field(default_factory=generate_id)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)


class DeviceCalibrationLog(Schema):
    """Schema for the historical calibration data of a given device"""

    __storage__ = StorageSpec(
        table="calibrations_logs", indexes=("name", "-last_calibrated")
    )
    model_config = ConfigDict(from_attributes=True)

    name: str
    version: str
    qubits: List[QubitCalibration]
    resonators: Optional[List[ResonatorCalibration]] = None
    couplers: Optional[List[CouplersCalibration]] = None
    discriminators: Optional[Dict[str, Any]] = None
    frames: Optional[List[PulseFrame]] = None
    defcals: Optional[List[GateDefcal]] = None
    last_calibrated: Optional[str] = Field(default_factory=get_current_timestamp)
    id: Id = Field(default_factory=generate_id)
    updated_at: Optional[str] = Field(default_factory=get_current_timestamp)


DeviceCalibrationQuery = create_partial_model(
    "DeviceCalibrationQuery",
    original=DeviceCalibration,
    default=Query(None),
    exclude=(
        "qubits",
        "resonators",
        "couplers",
        "discriminators",
        "frames",
        "defcals",
    ),
)
