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

import typing
from fnmatch import fnmatch
from typing import List, Optional, Type

import pytest
from pydantic import BaseModel

from api import app
from dev.openapi.export import SCHEMA_FILE, render_schema
from dev.openapi.generate import MODELS_FILE, render_models
from services.calibration.dtos import DeviceCalibrationCreate
from services.devices.dtos import DeviceSwitchData, DeviceUpsert
from services.external.bcc import events as bcc_events
from services.jobs.dtos import JobUpdate

# what a backend sends that MSS leaves out on purpose
_NOT_KEPT = (
    # the backend's own stage of the job, which the job's status stands for
    "stage",
    # computed by the backend from each stage's started and finished, which MSS keeps
    "timestamps.*.start_timestamp",
    "timestamps.*.finish_timestamp",
)


def test_committed_schema_matches_the_app():
    assert SCHEMA_FILE.read_text() == render_schema(app.openapi()), (
        f"{SCHEMA_FILE.name} is stale: run python -m dev.openapi.export"
    )


def test_backend_event_models_match_its_spec():
    """A changed spec, or a hand-edited model, fails until the models are regenerated"""
    assert MODELS_FILE.read_text() == render_models(), (
        f"{MODELS_FILE.name} is stale: run dev/openapi/sync.sh"
    )


@pytest.mark.parametrize(
    "sent, kept",
    [
        (bcc_events.Device, DeviceUpsert),
        (bcc_events.DeviceCalibration, DeviceCalibrationCreate),
        (bcc_events.Job, JobUpdate),
        (bcc_events.DeviceSwitchData, DeviceSwitchData),
    ],
    ids=lambda model: model.__name__,
)
def test_mss_keeps_every_field_a_backend_sends(sent, kept):
    """A field the backend's spec adds fails until MSS declares where it keeps it, as MSS
    drops what it does not declare"""
    missing = _get_missing_fields(sent, kept)

    assert [
        name for name in missing if not any(fnmatch(name, p) for p in _NOT_KEPT)
    ] == []


def _get_missing_fields(
    sent: Type[BaseModel], kept: Type[BaseModel], prefix: str = ""
) -> List[str]:
    """The fields of the sent model, and of the models it holds, that the kept one lacks"""
    missing = []
    for name, field in sent.model_fields.items():
        if name not in kept.model_fields:
            missing.append(f"{prefix}{name}")
            continue
        sent_model = _get_model(field.annotation)
        kept_model = _get_model(kept.model_fields[name].annotation)
        if sent_model and kept_model:
            missing += _get_missing_fields(sent_model, kept_model, f"{prefix}{name}.")
    return missing


def _get_model(annotation: object) -> Optional[Type[BaseModel]]:
    """The model the annotation holds, alone, optional or in a list"""
    pending = [annotation]
    while pending:
        item = pending.pop()
        if isinstance(item, type) and issubclass(item, BaseModel):
            return item
        pending.extend(typing.get_args(item))
    return None
