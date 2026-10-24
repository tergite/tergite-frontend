# This code is part of Tergite
#
# (C) Copyright François Voron 2019 (fastapi-users 14.0.2, MIT licence; see libs/authlib/LICENSE)
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import pytest

from libs.authlib.jwt import SecretType, decode_jwt, generate_jwt


@pytest.mark.jwt
def test_generate_decode_jwt(secret: SecretType):
    audience = "TEST_AUDIENCE"
    data = {"foo": "bar", "aud": audience}

    jwt = generate_jwt(data, secret, 3600)
    decoded = decode_jwt(jwt, secret, [audience])

    assert decoded["foo"] == "bar"
    assert decoded["aud"] == audience
