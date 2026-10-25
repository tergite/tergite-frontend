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

# a folder the packages install whole, as a onefile binary would unpack itself on every start
# nuitka-project: --standalone
# nuitka-project: --output-filename=mss
# nuitka-project: --include-package=fastapi
# nuitka-project: --include-package=uvicorn
# nuitka-project: --include-package=python_multipart
# nuitka-project: --include-package=httpx
# nuitka-project: --include-package=httpx_oauth
# nuitka-project: --include-package=email_validator
# nuitka-project: --include-package=cryptography
# nuitka-project: --include-package=websockets
# nuitka-project: --include-package=aiosmtplib
# nuitka-project: --include-package=loguru
# nuitka-project: --include-package=hiredis
# nuitka-project: --include-package=redis
# nuitka-project: --include-package=sqlalchemy
# nuitka-project: --include-package=pymongo
# nuitka-project: --include-package=aiosqlite
# nuitka-project: --include-package=jwt
# nuitka-project: --include-package=asyncpg
# nuitka-project: --include-package=pydantic
# nuitka-project: --include-package=alembic
# nuitka-project: --include-data-files={MAIN_DIRECTORY}/alembic.ini=alembic.ini
# nuitka-project: --include-data-files={MAIN_DIRECTORY}/migrations/env.py=migrations/env.py
# nuitka-project: --include-data-files={MAIN_DIRECTORY}/migrations/versions/*.py=migrations/versions/
# nuitka-project: --include-data-files={MAIN_DIRECTORY}/migrations/mongodb/*.json=migrations/mongodb/
# the dashboard's build, copied to ui/ before the build, which MSS serves at /ui
# nuitka-project: --include-data-dir={MAIN_DIRECTORY}/ui=ui

import argparse
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config
from pymongo import MongoClient

import migrations.mongodb
import settings
from api.rest import app
from api.rest.database import get_database_url

_ROOT = Path(__file__).parent


def main() -> None:
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
    args = parser.parse_args()

    if args.command in ("start", "migrate"):
        _migrate()
    if args.command in ("start", "serve"):
        port = args.port or settings.CONFIG.general.mss_port
        _serve(args.host, port, args.forwarded_allow_ips, args.reload)


def _migrate() -> None:
    """Brings the configured database to the latest schemas"""
    database_url = get_database_url(settings.CONFIG.database)
    if database_url.startswith("mongodb"):
        with MongoClient(database_url) as client:
            applied = migrations.mongodb.upgrade(client.get_default_database())
        print(f"MongoDB migrations applied: {applied or 'none pending'}")
    elif database_url.startswith("redis"):
        print("Redis migrations applied: none pending")
    else:
        command.upgrade(Config(str(_ROOT / "alembic.ini")), "head")


def _serve(host: str, port: int, forwarded_allow_ips: str | None, reload: bool) -> None:
    uvicorn.run(
        app,
        host=host,
        reload=reload,
        port=port,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips=forwarded_allow_ips,
    )


if __name__ == "__main__":
    main()
