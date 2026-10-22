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
from pathlib import Path

from dev.naming import (
    APP_ROOT,
    BASELINE_FILE,
    compare_with_baseline,
    find_violations,
    read_baseline,
)


def test_names_follow_the_naming_rules():
    new, fixed = compare_with_baseline(
        find_violations(APP_ROOT), read_baseline(BASELINE_FILE)
    )

    assert new == [], "\n".join(f"{v.location}: {v.rule}" for v in new)
    assert fixed == [], f"fixed, so delete from {BASELINE_FILE.name}: {fixed}"


def test_non_verb_function_names_are_flagged(tmp_path: Path):
    _write_module(tmp_path, "def job_status(): ...\ndef get_job_status(): ...\n")

    locations = [violation.location for violation in find_violations(tmp_path)]

    assert locations == ["utils/sample.py::job_status"]


def test_unprefixed_booleans_are_flagged(tmp_path: Path):
    _write_module(
        tmp_path,
        "class Job:\n"
        "    active: bool\n"
        "    is_done: bool\n"
        "def get_job(decrypt: bool, should_decrypt: bool): ...\n",
    )

    locations = [violation.location for violation in find_violations(tmp_path)]

    assert locations == [
        "utils/sample.py::Job.active",
        "utils/sample.py::get_job(decrypt)",
    ]


def test_properties_and_hooks_need_no_verb(tmp_path: Path):
    _write_module(
        tmp_path,
        "class User:\n"
        "    @property\n"
        "    def username(self): ...\n"
        "async def on_startup(): ...\n",
    )

    assert find_violations(tmp_path) == []


def _write_module(app_root: Path, source: str):
    (app_root / "utils").mkdir()
    (app_root / "utils" / "sample.py").write_text(source)
