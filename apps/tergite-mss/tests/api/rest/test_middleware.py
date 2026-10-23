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

import uuid


def test_a_request_is_recorded_with_its_id(client, db):
    request_id = str(uuid.uuid4())

    with client as client:
        response = client.get("/devices/", headers={"x-request-id": request_id})

    log = db["request_logs"].find_one({"request_id": request_id})
    assert response.headers["x-request-id"] == request_id
    assert log is not None
    assert log["expires_at"] > log["created_at"]


def test_a_request_without_an_id_gets_one(client, db):
    with client as client:
        response = client.get("/devices/")

    request_id = response.headers["x-request-id"]
    assert db["request_logs"].find_one({"request_id": request_id}) is not None
