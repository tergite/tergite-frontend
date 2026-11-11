# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Serves GET /refreshed-db, which reseeds the e2e stack's MSS and backend databases from
the fixtures: see dev/e2e_native_test.sh, which runs it in MSS's environment and config"""

import argparse
import sqlite3
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# the running backend's workers write to its database too, so wait out their locks
_LOCK_TIMEOUT_SECONDS = 5.0
_BOOKING_COLUMNS = "id, user_id, start_utc, end_utc, total_duration"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument(
        "--mss-path", required=True, help="the MSS checkout to seed with"
    )
    parser.add_argument(
        "--sql", required=True, help="the SQL to load into each database"
    )
    parser.add_argument(
        "databases",
        nargs="*",
        help="the backends' SQLite files, each in a folder named for its device",
    )
    args = parser.parse_args()

    class ResetHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/refreshed-db":
                self.send_error(404)
                return

            _reset(args.mss_path, args.sql, args.databases)
            body = b"success\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    HTTPServer(("127.0.0.1", args.port), ResetHandler).serve_forever()


def _reset(mss_path: str, sql: str, databases: list[str]) -> None:
    subprocess.run(
        [sys.executable, "-m", "dev.seed"],
        cwd=mss_path,
        check=True,
        capture_output=True,
    )
    script = Path(sql).read_text()
    for database in databases:
        _refill_backend_database(Path(database), script)


def _refill_backend_database(database: Path, script: str) -> None:
    """Runs the fixture's SQL on a backend's database, then gives it the fixture's bookings,
    as its device's own where the backend keys bookings by device"""
    connection = sqlite3.connect(database, timeout=_LOCK_TIMEOUT_SECONDS)
    try:
        connection.executescript(script)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(booking)")}
        if "device_name" in columns:
            connection.execute(
                f"INSERT INTO booking ({_BOOKING_COLUMNS}, device_name) "
                f"SELECT {_BOOKING_COLUMNS}, ? FROM fixture_booking",
                (database.parent.name,),
            )
        else:
            connection.execute(
                f"INSERT INTO booking ({_BOOKING_COLUMNS}) "
                f"SELECT {_BOOKING_COLUMNS} FROM fixture_booking"
            )
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
