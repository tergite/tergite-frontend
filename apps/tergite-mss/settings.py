# This code is part of Tergite
#
# (C) Copyright Miroslav Dobsicek 2021
# (C) Copyright Martin Ahindura 2023, 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import logging
import os
from pathlib import Path

from utils.config import AppConfig

_ROOT = Path(__file__).parent

_MSS_CONFIG_FILE = os.environ.get("MSS_CONFIG_FILE", default="mss-config.toml")
_MSS_CONFIG_JSON_STR = os.environ.get("MSS_CONFIG_JSON_STR")
PRIVATE_KEY_FILE = Path(
    os.getenv("PRIVATE_KEY_FILE", default=_ROOT / "private-mss-key.pem")
).resolve()
if not PRIVATE_KEY_FILE.exists():
    raise ValueError(f"private key file '{PRIVATE_KEY_FILE}' does not exist")

if _MSS_CONFIG_JSON_STR is not None:
    # Get the config from the JSON string if passed
    CONFIG: AppConfig = AppConfig.from_json_str(_MSS_CONFIG_JSON_STR)
else:
    CONFIG: AppConfig = AppConfig.from_toml(_MSS_CONFIG_FILE)

_is_production = CONFIG.environment == "production"
_is_puhuri_enabled = CONFIG.puhuri.is_enabled

# Logger
_logger_level = logging.INFO if _is_production else logging.WARN
root_logger = logging.getLogger()
root_logger.setLevel(_logger_level)

# PUHURI synchronization
if _is_puhuri_enabled and not CONFIG.puhuri.waldur_api_uri:
    raise ValueError(
        "'puhuri.waldur_api_uri' config variable must be set if 'puhuri.is_enabled' is true."
    )

if _is_puhuri_enabled and not CONFIG.puhuri.waldur_client_token:
    raise ValueError(
        "'puhuri.waldur_client_token' environment variable must be set if 'puhuri.is_enabled' is true."
    )

if _is_puhuri_enabled and not CONFIG.puhuri.provider_uuid:
    raise ValueError(
        "'puhuri.provider_uuid' config variable must be set if 'puhuri.is_enabled' is true."
    )
