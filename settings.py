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
from utils.logging import get_log_level

_ROOT = Path(__file__).parent

# the config and the key, when relative, are in the folder MSS starts in, as an installed
# MSS has no checkout to find them in
_MSS_CONFIG_JSON_STR = os.environ.get("MSS_CONFIG_JSON_STR")
_MSS_CONFIG_FILE = Path(
    os.environ.get("MSS_CONFIG_FILE", default="mss-config.toml")
).resolve()

# the private key for authentication between MSS and BCC
PRIVATE_KEY_FILE = Path(
    os.getenv("PRIVATE_KEY_FILE", default="private-mss-key.pem")
).resolve()
if not PRIVATE_KEY_FILE.exists():
    raise ValueError(f"private key file '{PRIVATE_KEY_FILE}' does not exist")

# the dashboard's build, which MSS serves at /ui when the folder exists; a checkout lacks
# the default one until `npm run build` in ui/
_MSS_DASHBOARD_DIR = os.environ.get("MSS_DASHBOARD_DIR")
DASHBOARD_DIR = Path(_MSS_DASHBOARD_DIR or _ROOT / "ui" / "dist").resolve()
if _MSS_DASHBOARD_DIR and not DASHBOARD_DIR.is_dir():
    raise ValueError(f"dashboard folder '{DASHBOARD_DIR}' does not exist")

if _MSS_CONFIG_JSON_STR:
    CONFIG: AppConfig = AppConfig.from_json_str(_MSS_CONFIG_JSON_STR)
elif _MSS_CONFIG_FILE.exists():
    CONFIG: AppConfig = AppConfig.parse_toml(_MSS_CONFIG_FILE)
else:
    raise ValueError("MSS config is empty")

logging.getLogger().setLevel(get_log_level(CONFIG.environment))
