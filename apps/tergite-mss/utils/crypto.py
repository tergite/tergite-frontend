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
"""Utilities for cryptography"""
import base64
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

_BCC_PUBLIC_KEYS: Dict[str, RSAPublicKey] = {}


def load_private_key(key_file: Path, password: Optional[bytes]) -> RSAPrivateKey:
    """Loads the MSS private key from its PEM file

    Args:
        key_file: the path to the private key file
        password: the password that the private key was encrypted with

    Returns:
        the private key of the MSS
    """
    with open(key_file, "rb") as file:
        return serialization.load_pem_private_key(file.read(), password=password)


def sign_message(private_key: RSAPrivateKey, message: str) -> str:
    """Creates an MSS-signed signature given a message

    Args:
        private_key: the MSS private key
        message: the message from MSS

    Returns:
        the string form of the signature
    """
    signature = private_key.sign(
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


def verify_ws_signature(signature: str, message: str, key_path: Path) -> None:
    """Verifies that the given message is from an approved source, given the signature

    Args:
        signature: the signature of the message signed by BCC
        message: the message from MSS
        key_path: the file path to the RSA public key PEM file

    Raises:
        InvalidSignature: if signature does not match with what would be expected from MSS
    """
    bcc_public_key = _get_bcc_public_key(key_path=key_path)
    bcc_public_key.verify(
        base64.b64decode(signature),
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256(),
    )


def decrypt_message(private_key: RSAPrivateKey, msg: str) -> str:
    """Decrypts the given message that has been encrypted with the MSS public key

    Args:
        private_key: the MSS private key
        msg: the message to decrypt

    Returns:
        the plain message
    """
    plain_msg = private_key.decrypt(
        base64.b64decode(msg),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return plain_msg.decode()


def get_uuid4_str():
    """Gets a UUID4 string"""
    return str(uuid4())


def _get_bcc_public_key(key_path: Path) -> RSAPublicKey:
    """Loads the public key of the BCC from the given PEM file, once per path

    Args:
        key_path: the file path to the RSA public key PEM file

    Returns:
        the public key of the BCC
    """
    key_path_str = str(key_path)

    if key_path_str not in _BCC_PUBLIC_KEYS:
        with open(key_path, "rb") as key_file:
            data = key_file.read()
            _BCC_PUBLIC_KEYS[key_path_str] = serialization.load_pem_public_key(data)

    return _BCC_PUBLIC_KEYS[key_path_str]
