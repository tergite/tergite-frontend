# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for the booking endpoints"""

# @pytest.mark.parametrize("user,booking,client", VALID_CREATE_BOOKINGS_PARAMS)
# def test_create_booking(client, user, booking: "_BasicBookingInfo"):
#     """POST '/bookings' should return the new booking created by the user"""
#     with client as client:
#         user_id, _ = _create_user(client, user=user)
#
#         # create booking
#         actual_booking_info, response = _create_booking(
#             client, user_id=user_id, booking=booking
#         )
#         actual_booking = response.json()
#
#         assert response.status_code == 200
#
#         assert actual_booking["id"] != ""
#         assert actual_booking_info["duration"] == booking["duration"]
#         assert actual_booking_info["starts_in"] == booking["starts_in"]
#         assert actual_booking["user_id"] == user_id
#
#
# @pytest.mark.parametrize("user,booking,client", INVALID_CREATE_BOOKINGS_PARAMS)
# def test_create_invalid_booking(client, user, booking: "_BasicBookingInfo"):
#     """Should return an error message if an attempt to create an invalid booking is made
#
#     e.g. start_utc in the past
#     """
#     with client as client:
#         user_id, _ = _create_user(client, user=user)
#         data = _to_booking_payload(booking)
#
#         # create booking
#         headers = create_mss_headers(user_id)
#         response = client.post("/bookings", headers=headers, json=data)
#         detail = f"{response.json()["detail"]}"
#
#         assert response.status_code == 422
#         assert booking["error_message"] in detail
#
#
# @pytest.mark.parametrize("user,booking,client", VALID_CREATE_BOOKINGS_PARAMS)
# def test_create_conflicting_booking(
#     client, user, booking: "_BasicBookingInfo", mocker: MockerFixture
# ):
#     """Should return an error message when creating a booking overlapping with another"""
#     with client as client:
#         user_id, _ = _create_user(client, user=user)
#
#         # create booking
#         _, response = _create_booking(client, user_id=user_id, booking=booking)
#         initial_slot = response.json()
#
#         # create another
#         overlapping_slot = {**booking, "duration": booking["duration"] + 10}
#         headers = create_mss_headers(user_id)
#         data = _to_booking_payload(overlapping_slot)
#         response = client.post("/bookings", headers=headers, json=data)
#
#         start_utc = datetime.fromisoformat(initial_slot["start_utc"]).replace(
#             tzinfo=None
#         )
#         end_utc = datetime.fromisoformat(initial_slot["end_utc"]).replace(tzinfo=None)
#         expected_err_msg = (
#             f"booking conflicts with another booking at {start_utc} to {end_utc}"
#         )
#         assert response.status_code == 409
#         assert response.json() == {"detail": expected_err_msg}
#
#
# @pytest.mark.parametrize("client", FASTAPI_CLIENTS)
# def test_create_too_many_booking(client):
#     """Returns error message when creating a booking when number of bookings in a period for user are maxed out."""
#     with client as client:
#         user = USERS[1]
#         user_id, _ = _create_user(client, user=user)
#
#         max_safe_idx = TEST_MAX_SLOTS_PER_DAY - 1
#
#         now = datetime.now(timezone.utc)
#         day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
#         day_end = day_start + timedelta(days=1)
#         expected_err = f"you have exceeded the maximum {TEST_MAX_SLOTS_PER_DAY} bookings per day for {day_start}-{day_end}"
#
#         # create many bookings
#         for idx, raw_item in enumerate(VALID_BOOKINGS):
#             headers = create_mss_headers(user_id)
#             data = _to_booking_payload(raw_item)
#             response = client.post("/bookings", headers=headers, json=data)
#             json_response = response.json()
#
#             if idx > max_safe_idx:
#                 assert expected_err in json_response["detail"]
#             else:
#                 assert response.status_code == 200
#
#
# @pytest.mark.parametrize("client, redis_conn, worker", CLIENT_AND_RQ_WORKER_TUPLES)
# def test_unauthenticated_create_booking(client, worker, redis_conn):
#     """Creating booking outside MSS errors out"""
#     with client as client:
#         headers = _get_headers("token")
#         data = _to_booking_payload(VALID_BOOKINGS[0])
#
#         response = client.post("/bookings", headers=headers, json=data)
#
#         assert response.status_code == 401
#         assert response.json() == {"detail": "user not authenticated"}
#
#         response = client.post("/bookings", json=data)
#
#         assert response.status_code == 401
#         assert response.json() == {"detail": "user not authenticated"}
#
#
# @pytest.mark.parametrize("pagination,client", _VIEW_MANY_PARAMS)
# def test_view_bookings(client, pagination: "_PaginationInfo"):
#     """GET "/bookings" shows paginated list of all available bookings"""
#     with client as client:
#         users = _create_many_users(client)
#         curr_user = users[0]
#         other_user = users[1]
#         curr_user_id = curr_user["id"]
#         other_user_id = other_user["id"]
#
#         # create bookings, for each user only upto TEST_MAX_SLOTS_PER_DAY
#         user_ids = [curr_user_id, other_user_id]
#         all_records = []
#         booking_data_list = VALID_BOOKINGS[: 2 * TEST_MAX_SLOTS_PER_DAY]
#         for idx, booking_info in enumerate(booking_data_list):
#             ids_idx = idx % 2
#             user_id = user_ids[ids_idx]
#             _, response = _create_booking(client, user_id=user_id, booking=booking_info)
#             all_records.append(response.json())
#
#         limit = pagination["limit"]
#         skip = pagination["skip"]
#
#         # view bookings
#         for user_id in user_ids:
#             response = _view_booking_list(
#                 client, user_id=user_id, skip=skip, limit=limit
#             )
#             actual_output = response.json()
#             expected = _paginate(all_records, skip=skip, limit=limit)
#
#             assert response.status_code == 200
#             assert actual_output == expected
#
#
# @pytest.mark.parametrize("client, redis_conn, worker", CLIENT_AND_RQ_WORKER_TUPLES)
# def test_unauthenticated_view_bookings(client, worker, redis_conn):
#     """Viewing bookings with non-existing user or outside MSS errors out"""
#     with client as client:
#         response = client.get("/bookings", headers=_get_headers("token"))
#
#         assert response.status_code == 401
#         assert response.json() == {"detail": "user not authenticated"}
#
#         response = client.get("/bookings")
#
#         assert response.status_code == 401
#         assert response.json() == {"detail": "user not authenticated"}
#
#
# @pytest.mark.parametrize("client, redis_conn, worker, job", _SIMPLE_UPLOAD_JOB_PARAMS)
# def test_cancel_future_booking(
#     client, worker, redis_conn, job, jobs_folder, mocker: MockerFixture
# ):
#     """POST '/booking/{id}/cancel' for a future booking, deletes the booking and allows jobs to run without it."""
#     with client as client:
#         users = _create_many_users(client)
#
#         # create booking
#         # third user; thus third job (duration: 2.1) belongs to them
#         booker = users[2]
#         booker_id = booker["id"]
#
#         booking_info = {"duration": 3, "starts_in": 2}
#         _, response = _create_booking(client, user_id=booker_id, booking=booking_info)
#         booking = Booking.model_validate(response.json())
#         assert response.status_code == 200
#
#         response = _cancel_booking(client, user_id=booker_id, booking_id=booking.id)
#         expected = {
#             "status": "success",
#             "detail": f"Booking of id {booking.id} cancelled",
#         }
#         got = response.json()
#
#         assert response.status_code == 200
#         assert got == expected
#
#         time.sleep(booking_info["starts_in"])
#         # Booking does not exist or work
#         # submit many jobs from many users when booking starts
#         raw_jobs = _get_raw_jobs(job, durations=[0.23, 1, 0.4, 0.5])
#         job_metadata_list = _get_job_submission_metadata(
#             client, users=users, jobs=raw_jobs, jobs_folder=jobs_folder, mocker=mocker
#         )
#         expected_job_ids = _submit_multiple_jobs_v2(client, data=job_metadata_list)
#
#         # Run the queue
#         worker.work(burst=True)
#
#         jobs_in_redis = _get_jobs_in_redis(redis_conn)
#
#         jobs_in_redis.sort(key=lambda v: v.start_utc)
#         job_ids = [job.job_id for job in jobs_in_redis]
#
#         assert all([v.status == JobStatus.SUCCESSFUL for v in jobs_in_redis])
#         assert job_ids == expected_job_ids
#
#
# @pytest.mark.parametrize("client", FASTAPI_CLIENTS)
# def test_admin_cancel_future_booking(client):
#     """Admin POST '/bookings/{id}/cancel' cancels any user's future booking"""
#     with client as client:
#         [user_1, user_2] = _create_many_users(client, raw_users=USERS[:2])
#
#         user_1_id = user_1["id"]
#         user_2_id = user_2["id"]
#
#         # create booking
#         booking_info = {"duration": 3, "starts_in": 2}
#         _, response = _create_booking(client, user_id=user_1_id, booking=booking_info)
#         booking = Booking.model_validate(response.json())
#
#         # Non-admins fail
#         # response = _cancel_booking(client, user_id=user_2_id, booking_id=booking.id)
#         # json_response = response.json()
#         # assert response.status_code == 404
#         # assert "not found" in json_response["detail"]
#
#         response = _cancel_booking(
#             client, user_id=user_2_id, booking_id=booking.id, is_admin=True
#         )
#         expected = {
#             "status": "success",
#             "detail": f"Booking of id {booking.id} cancelled",
#         }
#         got = response.json()
#
#         assert response.status_code == 200
#         assert got == expected
#
#
# @pytest.mark.parametrize(
#     "client, redis_conn, worker, job", _SIMPLE_UPLOAD_JOB_PARAMS[:-1]
# )
# def test_cancel_active_booking(
#     client, worker, redis_conn, job, jobs_folder, mocker: MockerFixture
# ):
#     """POST '/bookings/{id}/cancel' for an active booking fails."""
#     with client as client:
#         users = _create_many_users(client)
#
#         # create booking
#         # third user; thus third job (duration: 2.1) belongs to them
#         booker = users[2]
#         booker_user_id = booker["id"]
#         # duration: 3; max idle time = 1
#         booking_info = {"duration": 3, "starts_in": 0}
#         _, response = _create_booking(
#             client, user_id=booker_user_id, booking=booking_info
#         )
#         booking = Booking.model_validate(response.json())
#
#         response = _cancel_booking(
#             client, user_id=booker_user_id, booking_id=booking.id
#         )
#         expected = {"detail": f"the booking of id {booking.id} is already active"}
#         got = response.json()
#
#         assert response.status_code == 400
#         assert got == expected
#
#         # It still works
#         # submit many jobs from many users when booking starts
#         raw_jobs = _get_raw_jobs(job, durations=[0.23, 0.3, 0.1])
#         job_metadata_list = _get_job_submission_metadata(
#             client, jobs=raw_jobs, users=users, jobs_folder=jobs_folder, mocker=mocker
#         )
#         _submit_multiple_jobs_v2(client, data=job_metadata_list)
#
#         # Run the queue; try to wait for waitlist to transfer things to execution queue
#         _wait_on_rq_worker(worker, with_scheduler=True)
#
#         jobs_in_redis = _get_jobs_in_redis(redis_conn)
#
#         jobs_in_redis.sort(key=lambda v: v.timestamps.execution.start_timestamp)
#         booker_jobs = [job for job in jobs_in_redis if job.user_id == booker_user_id]
#         last_booker_job = booker_jobs[-1]
#
#         # Assert that they are all complete and their booker jobs started before booking end_utc
#         # while non booker jobs started after end_utc
#         # Note: Enqueue_at ignores microseconds
#         booking_end_timestamp = _drop_microsec(booking.end_utc)
#         last_booker_job_start = _drop_microsec(
#             last_booker_job.timestamps.execution.start_timestamp
#         )
#
#         assert all([v.status == JobStatus.SUCCESSFUL for v in jobs_in_redis])
#         assert last_booker_job_start < booking_end_timestamp
#
#
# @pytest.mark.parametrize("client, redis_conn, worker, job", _SIMPLE_UPLOAD_JOB_PARAMS)
# def test_cancel_completed_booking(
#     client, worker, redis_conn, job, mocker: MockerFixture
# ):
#     """POST '/bookings/{id}/cancel' for a completed booking fails."""
#     with client as client:
#         users = _create_many_users(client)
#
#         # create booking
#         booker = users[0]
#         booker_user_id = booker["id"]
#         # duration: 2; max idle time = 1
#         booking_info = {"duration": 2, "starts_in": 0}
#         _, response = _create_booking(
#             client, user_id=booker_user_id, booking=booking_info
#         )
#         booking = Booking.model_validate(response.json())
#
#         time.sleep(2)
#
#         response = _cancel_booking(
#             client, user_id=booker_user_id, booking_id=booking.id
#         )
#         expected = {"detail": f"the booking of id {booking.id} is already complete"}
#         got = response.json()
#
#         assert response.status_code == 400
#         assert got == expected
