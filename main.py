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

import argparse
import logging
import multiprocessing
import sys

import uvicorn

import settings


def main() -> None:
    """Runs the MSS command given on the command line: start, serve or migrate"""
    parser = argparse.ArgumentParser(
        description="Manage the Main Service Server (MSS)."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=["start", "serve", "migrate"],
        help="Migrate the database and serve the API (start, the default), "
        "only serve it, or only migrate the database and exit.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind socket to this host.")
    parser.add_argument(
        "--port",
        type=int,
        help="Bind socket to this port; default: the config's general.mss_port.",
    )
    parser.add_argument(
        "--forwarded-allow-ips",
        help="Allow forwarding of IPS only if done by the given IP.",
    )
    parser.add_argument(
        "--reload",
        default=False,
        action="store_true",
        help="Enable reload (not recommended for production binaries).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Number of worker processes; default: $WEB_CONCURRENCY, or 1. "
        "Not valid with --reload.",
    )
    args = parser.parse_args()

    if args.command == "start":
        _migrate_in_child()
    elif args.command == "migrate":
        _migrate()
    if args.command in ("start", "serve"):
        port = args.port or settings.CONFIG.general.mss_port
        _serve(args.host, port, args.forwarded_allow_ips, args.reload, args.workers)


def _migrate_in_child() -> None:
    """Migrates in a process of its own, so the server never holds Alembic and SQLAlchemy"""
    process = multiprocessing.Process(target=_migrate, name="migrate")
    process.start()
    process.join()
    if process.exitcode != 0:
        sys.exit(f"mss: migrating failed with exit code {process.exitcode}")


def _migrate() -> None:
    """Brings the configured database to the latest schemas"""
    # here, as importing them costs the server some 20 MiB
    from alembic import command
    from pymongo import MongoClient

    import migrations.mongodb
    from utils.migrations import get_alembic_config

    database_url = settings.CONFIG.database.full_url
    if database_url.startswith("mongodb"):
        with MongoClient(database_url) as client:
            applied = migrations.mongodb.upgrade(client.get_default_database())
        print(f"MongoDB migrations applied: {applied or 'none pending'}")
    else:
        # Alembic's progress, as alembic.ini's loggers print it when run by hand
        logging.basicConfig(format="%(levelname)-5.5s [%(name)s] %(message)s")
        logging.getLogger("alembic").setLevel(logging.INFO)
        command.upgrade(get_alembic_config(), "head")


def _serve(
    host: str,
    port: int,
    forwarded_allow_ips: str | None,
    reload: bool,
    workers: int | None,
) -> None:
    # by import string, as uvicorn reloads and runs workers only so
    uvicorn.run(
        "api:app",
        host=host,
        reload=reload,
        port=port,
        workers=workers,
        proxy_headers=True,
        forwarded_allow_ips=forwarded_allow_ips,
    )


if __name__ == "__main__":
    main()
