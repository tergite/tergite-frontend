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

import pytest

from tests._utils.auth import TEST_SUPERUSER_DICT, TEST_SYSTEM_USER_DICT, TEST_USER_DICT
from tests.conftest import get_auth_cookie
from utils.config import UserRole

_MY_USER_INFO_REQUESTS = [
    (user, get_auth_cookie(str(user["_id"])))
    for user in [TEST_USER_DICT, TEST_SUPERUSER_DICT, TEST_SYSTEM_USER_DICT]
]


@pytest.mark.parametrize("user, cookies", _MY_USER_INFO_REQUESTS)
def test_view_my_user_profile(user, cookies, client):
    """Any user can view only their own single user information at /me/profile"""
    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get("/me/profile", cookies=cookies)

        raw_data = response.json()
        got = {**raw_data, "roles": sorted(raw_data.get("roles"))}
        expected = {
            "id": str(user["_id"]),
            "email": user["email"],
            "is_active": True,
            "is_verified": user["is_verified"],
            "is_superuser": UserRole.ADMIN in user["roles"],
            "roles": sorted(user.get("roles")),
        }

        assert response.status_code == 200
        assert got == expected


# @pytest.mark.parametrize("client, redis_conn, worker, job", _SIMPLE_UPLOAD_JOB_PARAMS)
# def test_delete_profile(
#     client, worker, redis_conn, job, jobs_folder, mocker: MockerFixture
# ):
#     """DELETE '/me/profile' should delete their own user profile"""
#     with client as client:
#         users = _create_many_users(client, USERS[:2])
#         curr_user = users[0]
#         other_user = users[1]
#
#         curr_user_id = curr_user["id"]
#         other_user_id = other_user["id"]
#
#         # create many bookings for this user
#         for booking in VALID_BOOKINGS[:TEST_MAX_SLOTS_PER_DAY]:
#             _create_booking(client, user_id=curr_user_id, booking=booking)
#
#         # create a booking for other user
#         _create_booking(
#             client, user_id=other_user_id, booking={"starts_in": 8, "duration": 2}
#         )
#
#         # wait for the first booking to start
#         raw_jobs = _get_raw_jobs(job, durations=[0.23, 0.1, 0.23])
#         job_metadata_list = _get_job_submission_metadata(
#             client, jobs=raw_jobs, users=users, mocker=mocker, jobs_folder=jobs_folder
#         )
#         _submit_multiple_jobs_v2(client, data=job_metadata_list)
#
#         # This should also cancel any bookings and any jobs belonging to user
#         response = _delete_own_profile(client, user_id=curr_user_id)
#         assert response.status_code == 200
#         assert response.json() == {"status": "success", "detail": "Profile deleted"}
#
#         response = _view_own_profile(client, user_id=curr_user_id)
#         assert response.status_code == 404
#         assert response.json() == {"detail": "user not found"}
#
#         # Run the queue; try to wait for waitlist to transfer things to execution queue
#         _wait_on_rq_worker(worker, with_scheduler=True)
#
#         jobs_in_redis = _get_jobs_in_redis(redis_conn)
#
#         deleted_user_jobs = [
#             job for job in jobs_in_redis if job.user_id == curr_user_id
#         ]
#         other_user_jobs = [job for job in jobs_in_redis if job.user_id != curr_user_id]
#         failure_reason = "Cancelled on user deletion"
#
#         assert all([v.status == JobStatus.CANCELLED for v in deleted_user_jobs])
#         assert all([v.failure_reason == failure_reason for v in deleted_user_jobs])
#         assert all([v.status == JobStatus.SUCCESSFUL for v in other_user_jobs])
