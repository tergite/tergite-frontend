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
"""Integration tests for the Puhuri background jobs"""
from datetime import datetime
from time import sleep
from typing import List

import pytest
from waldur_client import ComponentUsage

from api.scripts import puhuri_sync
from services.auth import Project
from tests._utils.auth import TEST_PROJECT_EXT_ID, get_db_record
from tests._utils.bcc import create_bcc_headers
from tests._utils.env import TEST_PUHURI_POLL_INTERVAL
from tests._utils.fixtures import load_json_fixture
from tests._utils.json import to_json
from tests._utils.mongodb import find_in_collection, insert_in_collection
from tests._utils.records import order_by, pop_field, with_current_timestamps
from tests._utils.waldur import MockCall

_PUHURI_PENDING_ORDERS = load_json_fixture("puhuri_pending_orders.json")
_PUHURI_PARTIALLY_UPDATED_PROJECTS = load_json_fixture(
    "puhuri_partially_updated_projects.json"
)
_PUHURI_UPDATED_PROJECTS = load_json_fixture("puhuri_updated_projects.json")
_JOB_TIMESTAMPED_UPDATES = load_json_fixture("job_timestamped_updates.json")
_INTERNAL_RESOURCE_USAGES = load_json_fixture("internal_resource_usages.json")
_JOBS_LIST = load_json_fixture("job_list.json")
_JOBS_COLLECTION = "jobs"
_INTERNAL_USAGE_COLLECTION = "internal_resource_usages"
_PROJECTS_COLLECTION = "auth_projects"
_EXCLUDED_FIELDS = ["_id", "id"]
_DEVICES = ["Loke", "Loki"]


# @pytest.mark.sequential
@pytest.mark.parametrize("device", _DEVICES)
def test_save_resource_usages(db, client, project_id, device):
    """PUT to "/jobs/{job_id}" updates the resource usage in database for that project id"""
    project_id_str = f"{project_id}"
    job_list = [{**item, "project_id": project_id_str} for item in _JOBS_LIST]
    job_list = with_current_timestamps(
        job_list, fields=("updated_at", "created_at", "calibration_date")
    )
    insert_in_collection(database=db, collection_name=_JOBS_COLLECTION, data=job_list)
    initial_data = find_in_collection(
        db,
        collection_name=_INTERNAL_USAGE_COLLECTION,
        fields_to_exclude=_EXCLUDED_FIELDS,
    )
    project = get_db_record(db, schema=Project, _id=project_id_str)
    expected_usages: List[dict] = []

    url = f"/devices/ws/{device}"
    headers = create_bcc_headers(device)

    # using context manager to ensure on_startup runs
    with client as client:
        with client.websocket_connect(url, headers=headers) as client:
            # push job resource usages to MSS
            for payload in _JOB_TIMESTAMPED_UPDATES.copy():
                current_qpu_seconds = project["qpu_seconds"]
                job_id = payload["job_id"]
                client.send_json(
                    {
                        "name": "job_updated",
                        "data": payload,
                    }
                )
                response = client.receive_json()
                assert response["status"] == "success"

                project = get_db_record(db, schema=Project, _id=project_id_str)
                usage = round(current_qpu_seconds - project["qpu_seconds"], 1)
                if usage > 0:
                    expected_usages.append(
                        {
                            "job_id": job_id,
                            "project_id": TEST_PROJECT_EXT_ID,
                            "qpu_seconds": usage,
                            "is_processed": False,
                        }
                    )

        final_data = find_in_collection(
            db,
            collection_name=_INTERNAL_USAGE_COLLECTION,
            fields_to_exclude=_EXCLUDED_FIELDS,
        )
        now = datetime.now()
        created_on_timestamps: List[datetime] = pop_field(final_data, "created_on")

        assert initial_data == []
        assert [
            {**item, "qpu_seconds": round(item["qpu_seconds"], 1)}
            for item in final_data
        ] == expected_usages
        assert all([(x - now).total_seconds() < 30 for x in created_on_timestamps])


# @pytest.mark.sequential
def test_post_resource_usages(db, mock_puhuri_sync_calls):
    """Should post all accumulated resource usages at a given interval"""
    insert_in_collection(
        database=db,
        collection_name=_INTERNAL_USAGE_COLLECTION,
        data=[
            {**item, "created_on": datetime.now()} for item in _INTERNAL_RESOURCE_USAGES
        ],
    )

    assert mock_puhuri_sync_calls.empty()

    # wait for the script to run its tasks
    sleep(TEST_PUHURI_POLL_INTERVAL + 1)

    got = []
    while not mock_puhuri_sync_calls.empty():
        mock_call: MockCall = mock_puhuri_sync_calls.get()
        if mock_call["method"] == "create_component_usages":
            got.append(mock_call["kwargs"].copy())

    expected = [
        {
            "plan_period_uuid": "c0e15746796646f183d9f0d0096cf084",
            "usages": to_json(
                [
                    ComponentUsage(
                        type="pre-paid",
                        amount=2.24,
                        description="8042.9 QPU seconds",
                    )
                ],
            ),
        },
        {
            "plan_period_uuid": "b62a8f69b3d8497986a7769b75d735fe",
            "usages": to_json(
                [
                    ComponentUsage(
                        type="pre-paid",
                        amount=222.53,
                        description="801104.5 QPU seconds",
                    )
                ]
            ),
        },
    ]

    got = order_by(got, "plan_period_uuid")
    expected = order_by(expected, "plan_period_uuid")
    # FIXME: Very brittle test. Fix this
    # assert got == expected


# @pytest.mark.sequential
def test_update_internal_projects(db, mock_puhuri_sync_calls, existing_puhuri_projects):
    """Should update internal projects with that got from Puhuri, at a given interval"""
    initial_data = find_in_collection(
        db, collection_name=_PROJECTS_COLLECTION, fields_to_exclude=[]
    )

    # wait for the script to run its tasks
    sleep(TEST_PUHURI_POLL_INTERVAL + 1)

    final_data = find_in_collection(
        db, collection_name=_PROJECTS_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
    )

    order_approval_calls = []
    while not mock_puhuri_sync_calls.empty():
        mock_call: MockCall = mock_puhuri_sync_calls.get()
        if mock_call["method"] == "marketplace_order_approve_by_provider":
            order_approval_calls.extend(mock_call["args"])

    assert order_by(initial_data, "ext_id") == order_by(
        existing_puhuri_projects, "ext_id"
    )
    # FIXME: Very brittle test. Fix this
    # assert order_by(final_data, "ext_id") == order_by(
    #     _PUHURI_PARTIALLY_UPDATED_PROJECTS, "ext_id"
    # )

    # assert sorted(order_approval_calls) == [
    #     "a2e3c4d78ee64391b089ebf41cb029b5",
    #     "b20588bb5daf4131890fe25c2deb9fc6",
    #     "b385941c4ce84acd9827b50a796d31d3",
    #     "b385941c4ce84ecd9427b50a786d31d3",
    #     "ceb90e76c1a045cf98051eaf1a21214d",
    #     "df64f46f6c6a4a94be084a2493289bc9",
    # ]


# @pytest.mark.sequential
def test_update_internal_resource_allocations(
    db, mock_puhuri_sync_calls, existing_puhuri_projects
):
    """Should update the internal resource allocation quotas with that got from Puhuri, at twice the given interval"""
    initial_data = find_in_collection(
        db, collection_name=_PROJECTS_COLLECTION, fields_to_exclude=[]
    )

    # wait for the script to run its longer tasks also
    sleep((TEST_PUHURI_POLL_INTERVAL * 2) + 1)

    final_data = find_in_collection(
        db, collection_name=_PROJECTS_COLLECTION, fields_to_exclude=_EXCLUDED_FIELDS
    )

    assert order_by(initial_data, "ext_id") == order_by(
        existing_puhuri_projects, "ext_id"
    )
    # FIXME: Very brittle test. Fix this
    # assert order_by(final_data, "ext_id") == order_by(
    #     _PUHURI_UPDATED_PROJECTS, "ext_id"
    # )


def test_puhuri_sync_enabled(mock_puhuri_synchronize):
    """Should start puhuri synchronizer if 'puhuri.is_enabled' config variable is true"""
    puhuri_sync.main([])
    mock_puhuri_synchronize.assert_called()


def test_puhuri_sync_disabled(disabled_puhuri_sync, mock_puhuri_synchronize):
    """Should not start puhuri synchronizer if 'puhuri.is_enabled' config variable is false"""
    with pytest.raises(
        ValueError,
        match="'puhuri.is_enabled' config variable is false",
    ):
        puhuri_sync.main([])

    mock_puhuri_synchronize.assert_not_called()


@pytest.mark.parametrize("arg", ["--ignore-if-disabled", "-i"])
def test_puhuri_sync_ignore_if_disabled_when_disabled(
    disabled_puhuri_sync, mock_puhuri_synchronize, arg
):
    """Should not raise any error with --ignore-if-disabled is passed as an argument"""
    puhuri_sync.main([arg])
    mock_puhuri_synchronize.assert_not_called()


@pytest.mark.parametrize("arg", ["--ignore-if-disabled", "-i"])
def test_puhuri_sync_ignore_if_disabled_when_enabled(mock_puhuri_synchronize, arg):
    """Should call puhuri.cynchronize when --ignore-if-disabled is passed as an argument"""
    puhuri_sync.main([arg])
    mock_puhuri_synchronize.assert_called()
