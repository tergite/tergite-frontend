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

_MSS_CONFIG_JSON_STR = os.environ.get("MSS_CONFIG_JSON_STR")
# the private key for authentication between MSS and BCC
PRIVATE_KEY_FILE = Path(
    os.getenv("PRIVATE_KEY_FILE", default=_ROOT / "private-mss-key.pem")
).resolve()
if not PRIVATE_KEY_FILE.exists():
    raise ValueError(f"private key file '{PRIVATE_KEY_FILE}' does not exist")

if not _MSS_CONFIG_JSON_STR:
    raise ValueError("MSS config is empty")

CONFIG: AppConfig = AppConfig.from_json_str(_MSS_CONFIG_JSON_STR)
PRIVATE_KEY_PASSWORD = CONFIG.private_key_password

_is_production = CONFIG.environment == "production"

# Logger
if _is_production:
    _logger_level = logging.INFO
elif CONFIG.environment == "test":
    _logger_level = logging.WARNING
else:
    _logger_level = logging.DEBUG

root_logger = logging.getLogger()
root_logger.setLevel(_logger_level)
