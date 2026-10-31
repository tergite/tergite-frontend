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
"""Compares a run of dev/perf/record.sh with the baseline; exits 1 if any measure is worse than allowed"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ALLOWED_WORSENING = 0.10
# a rise this small is noise however large it is relative to the baseline, which may be 0
NOISE_FLOORS = {"ms": 10, "bytes": 1024, "MiB": 5, "connections": 2, "failures": 0}
MEMORY_UNITS_IN_MIB = {"B": 1 / 1024**2, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}


def main(baseline_path: Path, run_path: Path) -> int:
    baseline = read_measures(baseline_path)
    run = read_measures(run_path)
    worse = [
        name
        for name in sorted(baseline)
        if is_worse(name, baseline[name], run.get(name))
    ]
    print_table(baseline, run, worse)
    return 1 if worse else 0


def read_measures(path: Path) -> dict[str, float]:
    return {
        **read_latencies(path / "locust_stats.csv"),
        **read_peaks(path / "process-stats.csv", "process", "memory", "memory MiB"),
        **read_peaks(
            path / "connections.csv", "database", "connections", "connections"
        ),
        **read_page_measures(path / "lighthouse" / "manifest.json"),
    }


def is_worse(name: str, baseline: float, run: float | None) -> bool:
    if run is None:
        return True
    rise = run - baseline
    unit = name.split(":")[0].split()[-1]
    return rise > NOISE_FLOORS[unit] and rise > baseline * ALLOWED_WORSENING


def print_table(baseline: dict[str, float], run: dict[str, float], worse: list[str]):
    for name in sorted(baseline):
        value = run.get(name, float("nan"))
        change = (
            f"{(value - baseline[name]) / baseline[name]:+.0%}"
            if baseline[name]
            else ""
        )
        mark = "  WORSE" if name in worse else ""
        print(f"{name:<60} {baseline[name]:>12.1f} {value:>12.1f} {change:>6}{mark}")


def read_latencies(path: Path) -> dict[str, float]:
    measures = {}
    for row in _read_csv(path):
        route = f"{row['Type']} {row['Name']}".strip()
        measures[f"p95 ms: {route}"] = float(row["95%"])
        measures[f"failures: {route}"] = float(row["Failure Count"])
    return measures


def read_peaks(path: Path, key: str, value: str, label: str) -> dict[str, float]:
    peaks = defaultdict(float)
    for row in _read_csv(path):
        if row[value].strip():
            peaks[f"peak {label}: {row[key]}"] = max(
                peaks[f"peak {label}: {row[key]}"], _parse_quantity(row[value])
            )
    return dict(peaks)


def read_page_measures(manifest_path: Path) -> dict[str, float]:
    measures = {}
    for entry in json.loads(manifest_path.read_text()):
        if not entry["isRepresentativeRun"]:
            continue
        # the manifest holds absolute paths of the machine that recorded it
        report_path = manifest_path.parent / Path(entry["jsonPath"]).name
        audits = json.loads(report_path.read_text())["audits"]
        page = urlsplit(entry["url"]).path
        scripts = audits["resource-summary"]["details"]["items"]
        measures[f"LCP ms: {page}"] = audits["largest-contentful-paint"]["numericValue"]
        measures[f"TBT ms: {page}"] = audits["total-blocking-time"]["numericValue"]
        measures[f"bytes: {page}"] = audits["total-byte-weight"]["numericValue"]
        measures[f"script bytes: {page}"] = next(
            v["transferSize"] for v in scripts if v["resourceType"] == "script"
        )
    return measures


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open() as file:
        return list(csv.DictReader(file))


def _parse_quantity(text: str) -> float:
    """'123.4MiB / 7.6GiB' is 123.4 MiB; a bare number is itself"""
    match = re.match(r"\s*([\d.]+)\s*([KMG]?i?B)?", text)
    return float(match.group(1)) * MEMORY_UNITS_IN_MIB.get(match.group(2) or "MiB", 1)


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
