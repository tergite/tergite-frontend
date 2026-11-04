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
"""Tests of the settings read from the environment, each in a fresh interpreter, as
settings reads them once on import"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parents[1]


def test_dashboard_dir_defaults_to_ui_dist():
    result = _import_settings({}, "print(settings.DASHBOARD_DIR)")
    assert result.stdout.strip() == str((_ROOT / "ui" / "dist").resolve())


def test_dashboard_dir_is_read_from_env(tmp_path):
    result = _import_settings(
        {"MSS_DASHBOARD_DIR": str(tmp_path)}, "print(settings.DASHBOARD_DIR)"
    )
    assert result.stdout.strip() == str(tmp_path.resolve())


def test_missing_dashboard_dir_from_env_fails(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        _import_settings({"MSS_DASHBOARD_DIR": str(missing)}, "")
    assert f"dashboard folder '{missing}' does not exist" in exc_info.value.stderr


def _import_settings(env: dict[str, str], code: str) -> subprocess.CompletedProcess:
    """Imports settings in a fresh interpreter with the test environment and env, then
    runs code"""
    environ = {k: v for k, v in os.environ.items() if k != "MSS_DASHBOARD_DIR"}
    return subprocess.run(
        [sys.executable, "-c", f"import settings\n{code}"],
        cwd=_ROOT,
        env={**environ, **env},
        capture_output=True,
        text=True,
        check=True,
    )
