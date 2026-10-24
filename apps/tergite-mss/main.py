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

# nuitka-project: --onefile
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

import argparse

import uvicorn

from api.rest import app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the compiled FastAPI application."
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind socket to this host.")
    parser.add_argument(
        "--port", type=int, default=8002, help="Bind socket to this port."
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

    uvicorn.run(
        app,
        host=args.host,
        reload=args.reload,
        port=args.port,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips=args.forwarded_allow_ips,
    )
