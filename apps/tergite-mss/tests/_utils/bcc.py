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
"""Utilities for mocking requests to BCC"""
import base64
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, NotRequired, Optional, TypedDict

import httpx
import jwt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from jwt import InvalidTokenError
from pydantic import BaseModel, model_validator

from services.external.bcc import BccClientHeaders
from tests._utils.env import TEST_JWT_SECRET, TEST_MSS_PUBLIC_KEY_PATH
from tests._utils.fixtures import get_fixture_path

_MSS_PUBLIC_KEY: Optional[RSAPublicKey] = None
_BCC_PRIVATE_KEYS: Dict[str, RSAPrivateKey] = {}
_BCC_PRIVATE_KEY_PATHS: Dict[str, str] = {
    "Loke": get_fixture_path("private-loke-key.pem"),
    "Loki": get_fixture_path("private-loki-key.pem"),
    "Pingu": get_fixture_path("private-pingu-key.pem"),
    "Pegu": get_fixture_path("private-pegu-key.pem"),
    "Thor": get_fixture_path("private-thor-key.pem"),
    "Likee": get_fixture_path("private-likee-key.pem"),
    "Thea": get_fixture_path("private-thea-key.pem"),
    "WrongCert": get_fixture_path("private-wrong-cert-key.pem"),
}


def create_bcc_client_jwt_token(user_id: str, job_id: str) -> str:
    """Creates a JWT token that works for jobs submitted via MSS

    Note that extra claims `exp` and `sub` get overridden
    so don't set them directly

    Args:
        user_id: the unique identifier of the user for whom the token is to be created
        job_id: the unique identifier fo the job from MSS

    Returns:
        the JWT token
    """
    exp = datetime.now(timezone.utc) + timedelta(seconds=45)
    payload = dict(job=job_id, exp=exp, sub=user_id)
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def encrypt_jwt_token(token: str) -> str:
    """Encrypts the token passed so that it is only readable by the right MSS instance

    Args:
        token: the raw token to encrypt

    Returns:
        the encrypted token
    """
    mss_pub_key = _get_mss_public_key()
    cipher_bytes = mss_pub_key.encrypt(
        token.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(cipher_bytes).decode()


def verify_mss_signature(signature: str, message: str) -> None:
    """Verifies that the given message is from MSS, given the signature

    Args:
        signature: the signature of the message signed by MSS
        message: the message from MSS

    Raises:
        InvalidSignature: if signature does not match with what would be expected from MSS
    """
    mss_pub_key = _get_mss_public_key()
    mss_pub_key.verify(
        base64.b64decode(signature),
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256(),
    )


def get_bcc_client_verified_headers(request: httpx.Request) -> BccClientHeaders:
    """Gets the headers from the request and verifies them

    Args:
        request: the httpx.Request from which to retrieve headers from

    Returns:
        The dictionary of headers used in accessing BCC if they are verified

    Raises:
        ValueError: headers not verified: {exp}
    """
    headers = request.headers
    names = (
        "x-mss-request-id",
        "x-mss-timestamp",
        "x-mss-signature",
        "x-mss-user-id",
        "x-mss-is-admin",
    )
    bcc_headers = {k: headers[k] for k in names if k in headers}

    try:
        user_id = bcc_headers["x-mss-user-id"]
        nonce = bcc_headers["x-mss-request-id"]
        timestamp = bcc_headers["x-mss-timestamp"]
        signature = bcc_headers["x-mss-signature"]

        message = f"{user_id}-{nonce}-{timestamp}"
        verify_mss_signature(signature=signature, message=message)

        return bcc_headers
    except (KeyError, ValueError, InvalidSignature) as exp:
        raise ValueError(f"headers not verified: {exp}")


def get_user_job_id_pair_from_token(token: str) -> tuple[str, str]:
    """Gets the user_id and the job_id from the given JWT token

    Args:
        token: the JWT token of the user

    Returns:
        the tuple of user_id, job_id from the token

    Raises:
        ValueError: not authenticated
    """
    try:
        payload = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        user_id, job_id = payload["sub"], payload["job"]
        if user_id is None:
            raise ValueError("user_id is None")

        return user_id, job_id
    except (InvalidTokenError, KeyError, ValueError) as exp:
        raise ValueError("not authenticated")


def to_booking_payload(booking_info: "BasicBookingInfo") -> "BookingPayload":
    """Converts the booking info to payload for creation of a new booking

    Args:
        booking_info: the basic booking info containing starts_in, duration

    Returns:
        the payload for creating a booking
    """
    starts_in = timedelta(seconds=booking_info["starts_in"])
    duration = timedelta(seconds=booking_info["duration"])

    current_timestamp = datetime.now(timezone.utc)
    start_utc = current_timestamp + starts_in
    end_utc = start_utc + duration
    return {
        "start_utc": start_utc.isoformat().replace("+00:00", "Z"),
        "end_utc": end_utc.isoformat().replace("+00:00", "Z"),
    }


def create_bcc_headers(device: str) -> Dict[str, str]:
    """Creates headers to show that the request is a valid one from BCC

    Args:
        device: the name of the device

    Returns:
        The dictionary of headers that show a given request is from BCC
    """
    request_id = f"{uuid.uuid4()}"
    timestamp = time.time()
    message = f"{device}-{request_id}-{timestamp}"
    signature = create_bcc_signature(device, message)
    headers = {
        "x-request-id": request_id,
        "x-timestamp": f"{timestamp}",
        "x-signature": signature,
        "x-id": device,
    }

    return headers


def create_bcc_signature(device: str, message: str) -> str:
    """Creates an BCC-signed signature given a message

    Args:
        device: the name of the BCC device
        message: the message from BCC

    Returns:
        the string form of the signature
    """
    bcc_private_key = _get_bcc_private_key(device)
    signature = bcc_private_key.sign(
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


def _get_bcc_private_key(device) -> RSAPrivateKey:
    """Loads the private key for the BCC device

    Returns:
        the private key of the BCC device
    """
    global _BCC_PRIVATE_KEYS

    private_key_path = _BCC_PRIVATE_KEY_PATHS[device]

    try:
        return _BCC_PRIVATE_KEYS[private_key_path]
    except KeyError:
        with open(private_key_path, "rb") as file:
            private_key = serialization.load_pem_private_key(file.read(), password=None)
            _BCC_PRIVATE_KEYS[private_key_path] = private_key
            return private_key


def _get_mss_public_key():
    """Loads the public key for MSS given the path to the key file

    Returns:
        the public key of the MSS
    """
    global _MSS_PUBLIC_KEY

    if not _MSS_PUBLIC_KEY:
        with open(TEST_MSS_PUBLIC_KEY_PATH, "rb") as key_file:
            data = key_file.read()
            _MSS_PUBLIC_KEY = serialization.load_pem_public_key(data)

    return _MSS_PUBLIC_KEY


class CreatedBooking(BaseModel):
    """Schema for the test created booking"""

    id: str = str(uuid.uuid4())
    total_duration: float = 0
    user_id: Optional[str] = None
    start_utc: datetime
    end_utc: datetime

    @model_validator(mode="after")
    def compute_duration(self):
        """Computes the duration automatically from start_utc and end_utc"""
        self.total_duration = (self.end_utc - self.start_utc).total_seconds()
        return self


class BasicBookingInfo(TypedDict):
    """The simplified basic booking info"""

    starts_in: float
    duration: float
    error_message: NotRequired[str]


class BookingPayload(TypedDict):
    """The payload for creation of a booking"""

    start_utc: str
    end_utc: str
