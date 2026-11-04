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
"""The MSS load scenario of the performance baselines, over the e2e fixtures; dev/perf/record.sh runs it"""

import time
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
import pymongo
from bson import ObjectId
from locust import HttpUser, between, events, task

FIXTURES_PATH = Path(__file__).parents[2] / "ui" / "fixtures"
MSS_CONFIG = tomllib.loads((FIXTURES_PATH / "mss-config.toml").read_text())
MONGODB_URL = "mongodb://127.0.0.1:27019"
DASHBOARD_USER_ID = "4939a0b9a7742e2cc52289e0"
DASHBOARD_PROJECT_ID = "653a8f19e736d76276597a6c"
# the system user's token, which dev.seed inserts
SDK_APP_TOKEN = "W0imS_n_J5ZwP8wFYvbBCiDkJVhQcEROEfyTPvFko1E"
SDK_USER_ID = ObjectId("5ddc8d9fb69602723cd3c38f")
SDK_PROJECT_ID = ObjectId("653a81b2e736d76276597a6b")
# the fixtures hold six jobs; the job list is only measured with a realistic length
JOB_COUNT = 500
SESSION_TTL_SECONDS = 24 * 3600


@events.test_start.add_listener
def insert_jobs(**_kwargs):
    with pymongo.MongoClient(MONGODB_URL) as client:
        jobs = client[MSS_CONFIG["database"]["name"]]["jobs"]
        jobs.insert_many([_build_job() for _ in range(JOB_COUNT)])


class DashboardUser(HttpUser):
    """Browses as the dashboard does, with the session cookie"""

    wait_time = between(0.5, 1.5)

    def on_start(self):
        auth = MSS_CONFIG["auth"]
        self.client.cookies.set(auth["cookie_name"], _sign_session(auth["jwt_secret"]))

    @task(4)
    def list_devices(self):
        self.client.get("/devices/")

    @task(2)
    def list_calibrations(self):
        self.client.get("/calibrations/")

    @task(2)
    def read_profile(self):
        self.client.get("/me/profile")

    @task(2)
    def list_projects(self):
        self.client.get("/me/projects/")

    @task(2)
    def list_notices(self):
        self.client.get("/me/notices/")

    @task(1)
    def create_and_delete_token(self):
        title = f"perf-{uuid.uuid4()}"
        self.client.post(
            "/me/tokens/",
            json={
                "title": title,
                "project_id": DASHBOARD_PROJECT_ID,
                "lifespan_seconds": 3600,
            },
        )
        # the token string is never listed, so the unique title finds it
        tokens = self.client.get("/me/tokens/").json()["data"]
        for token_id in [v["id"] for v in tokens if v["title"] == title]:
            self.client.delete(f"/me/tokens/{token_id}", name="/me/tokens/{id}")


class SdkUser(HttpUser):
    """Polls jobs as the SDK does, with the app token"""

    wait_time = between(0.5, 1.5)

    def on_start(self):
        self.client.headers["Authorization"] = f"Bearer {SDK_APP_TOKEN}"

    @task
    def list_jobs(self):
        self.client.get("/jobs/")


def _sign_session(secret: str) -> str:
    claims = {
        "sub": DASHBOARD_USER_ID,
        "aud": ["fastapi-users:auth"],
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def _build_job() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "job_id": str(uuid.uuid4()),
        "device": "Loke",
        "calibration_date": now,
        "project_id": SDK_PROJECT_ID,
        "user_id": SDK_USER_ID,
        "status": "successful",
        "created_at": now,
        "updated_at": now,
    }
