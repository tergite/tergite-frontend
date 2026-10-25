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

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dashboard import include_dashboard


@pytest.fixture
def dashboard_client(tmp_path) -> TestClient:
    (tmp_path / "index.html").write_text("<html>dashboard</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index.js").write_text("console.log('dashboard')")
    app = FastAPI()
    include_dashboard(app, tmp_path)
    return TestClient(app)


def test_root_redirects_to_dashboard(dashboard_client):
    response = dashboard_client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"


@pytest.mark.parametrize("path", ["/ui", "/ui/", "/ui/devices/loke"])
def test_pages_get_index_html(dashboard_client, path):
    response = dashboard_client.get(path)
    assert response.status_code == 200
    assert response.text == "<html>dashboard</html>"


def test_files_are_served(dashboard_client):
    response = dashboard_client.get("/ui/assets/index.js")
    assert response.status_code == 200
    assert response.text == "console.log('dashboard')"
