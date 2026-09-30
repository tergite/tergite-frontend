# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2024, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from datetime import datetime, timezone

import pytest

from tests.conftest import BACKEND_SLUGS


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_init_recalibration(
    client, admin_jwt_cookie, user_jwt_cookie, backend, mock_bcc
):
    """POST '/admin/bcc/recalibration/{backend}/init' should start recalibration via MSS"""
    with client as client:
        params = {
            "interval": 3000,
            "start_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # non admins are not allowed
        response = client.post(
            f"/admin/bcc/recalibration/{backend}/init",
            cookies=user_jwt_cookie,
            params=params,
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.post(
            f"/admin/bcc/recalibration/{backend}/init",
            cookies=admin_jwt_cookie,
            params=params,
        )
        actual_output = response.json()

        assert response.status_code == 200
        assert actual_output == {"status": "success"}


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_get_recalibration_info(
    client,
    admin_jwt_cookie,
    user_jwt_cookie,
    backend,
    mock_bcc,
):
    """GET '/admin/bcc/recalibration/{backend}/info' should get recalibration info via MSS"""
    with client as client:
        # non admins are not allowed
        response = client.get(
            f"/admin/bcc/recalibration/{backend}/info", cookies=user_jwt_cookie
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.get(
            f"/admin/bcc/recalibration/{backend}/info", cookies=admin_jwt_cookie
        )
        actual_output = response.json()

        assert response.status_code == 200
        assert actual_output == {
            "current_job_id": None,
            "current_job_status": None,
            "current_job_started_at": None,
            "previous_job_id": "last_finished_rq_job_id",
            "previous_job_status": "finished",
            "previous_job_started_at": "2026-04-27T00:00:25.495000Z",
            "previous_job_ended_at": "2026-04-27T00:00:25.495000Z",
            "previous_job_error": None,
            "next_job_id": "next_rq_job_id",
            "next_job_status": "scheduled",
            "next_job_enqueued_at": None,
            "interval": 4000.0,
        }


@pytest.mark.parametrize("backend", BACKEND_SLUGS)
def test_admin_cancel_recalibration(
    client, admin_jwt_cookie, user_jwt_cookie, backend, mock_bcc
):
    """POST '/admin/bcc/recalibration/{backend}/cancel' should stop recalibration via MSS"""
    with client as client:
        params = {
            "ignore_errors": True,
        }
        # non admins are not allowed
        response = client.post(
            f"/admin/bcc/recalibration/{backend}/cancel",
            cookies=user_jwt_cookie,
            params=params,
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

        # admins are allowed
        response = client.post(
            f"/admin/bcc/recalibration/{backend}/cancel",
            cookies=admin_jwt_cookie,
            params=params,
        )
        actual_output = response.json()

        assert response.status_code == 200
        assert actual_output == {"status": "success"}
