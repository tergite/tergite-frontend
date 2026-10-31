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

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

# under a prefix of its own, as its pages, e.g. /devices, are API paths too
DASHBOARD_PATH = "/ui"


def include_dashboard(app: FastAPI, directory: Path) -> None:
    """Serves the dashboard's build in directory at /ui, and redirects / to it

    Args:
        app: the FastAPI app to serve the dashboard on
        directory: the folder holding the dashboard's build
    """
    app.mount(DASHBOARD_PATH, _SinglePageApp(directory=directory), name="dashboard")

    @app.get("/", include_in_schema=False)
    async def redirect_to_dashboard() -> RedirectResponse:
        return RedirectResponse(f"{DASHBOARD_PATH}/")


class _SinglePageApp(StaticFiles):
    """Serves index.html for the paths no file has, as the dashboard routes them itself"""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)
