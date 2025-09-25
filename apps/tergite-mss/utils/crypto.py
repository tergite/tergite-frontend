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
from typing import Dict

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

_MSS_PRIVATE_KEYS: Dict[str, RSAPrivateKey] = {}


def sign_message(key_file: Path, message: str) -> str:
    """Creates an MSS-signed signature given a message

    Args:
        key_file: the path to the private RSA key
        message: the message from MSS

    Returns:
        the string form of the signature
    """
    mss_private_key = _get_private_key(key_file)
    signature = mss_private_key.sign(
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


def decrypt_message(
    private_key_file: Path,
    msg: str,
) -> str:
    """Decrypts the given message that has been encrypted with the MSS public key

    Args:
        msg: the message to decrypt
        private_key_file: the file path to the RSA private key PEM file

    Returns:
        the plain message
    """
    key = _get_private_key(private_key_file)
    cipher_bytes = base64.b64decode(msg)
    plain_msg = key.decrypt(
        cipher_bytes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return plain_msg.decode()


def _get_private_key(key_file: Path) -> RSAPrivateKey:
    """Loads the private key for MSS

    Args:
        key_file: the path to the private key file

    Returns:
        the private key of the MSS
    """
    global _MSS_PRIVATE_KEYS

    key_file_str = str(key_file)

    try:
        return _MSS_PRIVATE_KEYS[key_file_str]
    except KeyError:
        with open(key_file, "rb") as file:
            key = _MSS_PRIVATE_KEYS[key_file_str] = serialization.load_pem_private_key(
                file.read(), password=None
            )
        return key
