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

from services.bcc_nonces import BccNonce


def test_a_request_keeps_the_id_it_was_sent_with(client):
    request_id = str(uuid.uuid4())

    with client as client:
        response = client.get("/devices/", headers={"x-request-id": request_id})

    assert response.headers["x-request-id"] == request_id


def test_a_request_without_an_id_gets_a_new_one(client):
    with client as client:
        first = client.get("/devices/").headers["x-request-id"]
        second = client.get("/devices/").headers["x-request-id"]

    assert uuid.UUID(first).version == 4 and first != second


def test_an_http_request_is_not_recorded(client, db):
    """Only a backend's websocket nonce is, as nothing would read an HTTP request's back"""
    with client as client:
        client.get("/devices/", headers={"x-request-id": str(uuid.uuid4())})

    assert db.count(BccNonce) == 0
