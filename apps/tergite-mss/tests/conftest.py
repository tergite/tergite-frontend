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


from tests._utils.env import TEST_DATABASE_URL, TEST_REDIS_URL, setup_test_env
from tests._utils.types import stub_pydantic_match_type_for_freezegun

# Set up the test environment before any other imports are made
setup_test_env()
# See: https://github.com/pydantic/pydantic/discussions/9343#discussioncomment-10723743
stub_pydantic_match_type_for_freezegun()

import settings
from utils.date_time import set_datetime_precision

# as the app does at startup, before any helper writes a timestamp
set_datetime_precision(settings.CONFIG.datetime_precision)

import asyncio
import random
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

import aiosmtplib
import pytest
import redis
from fastapi.testclient import TestClient
from pydantic import AnyUrl

from libs.storage import derive_id
from tests._utils.auth import (
    TEST_APP_TOKEN_STRING,
    TEST_NO_QPU_APP_TOKEN_STRING,
    TEST_OUTSIDER_ID,
    TEST_PROJECT_ID,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_APP_TOKEN_STRING,
    TEST_SYSTEM_USER_ID,
    TEST_USER_DICT,
    TEST_USER_ID,
    get_auth_cookie,
    init_test_auth,
)
from tests._utils.fixtures import load_json_fixture
from tests._utils.records import with_offset_datetimes
from tests._utils.storage import (
    DATABASE_KINDS,
    SQL_DATABASE_KINDS,
    SyncDatabase,
    empty_database,
    get_database_url,
    get_sql_database_url,
    insert_if_not_exist,
    reset_database,
    reset_sql_database,
)

BACKEND_SLUGS = ("Loke", "Pingu")
PROJECT_LIST = load_json_fixture("project_list.json")
APP_TOKEN_LIST = load_json_fixture("app_token_list.json")
NOTICE_LIST = load_json_fixture("notices.json")
USER_REQUEST_LIST = load_json_fixture("user_requests.json")
pytest_plugins = ["tests._utils.oauth", "tests._utils.mock_backend"]
# fixtures that change what the app starts with, so it must start afresh
_FRESH_APP_FIXTURES = {"unconfigured_email"}
_SCHEMAS_KEPT_ACROSS_TESTS = {"NoticeTemplate", "Role"}


@pytest.fixture(scope="session")
def api_database() -> Generator[SyncDatabase, Any, None]:
    """The database the app runs on: the one TEST_DATABASE_URL names, emptied first"""
    from api.rest.database import SCHEMAS
    from services.auth import ensure_roles

    asyncio.run(empty_database(TEST_DATABASE_URL))
    settings.CONFIG.database.url = AnyUrl(TEST_DATABASE_URL)
    database = SyncDatabase(TEST_DATABASE_URL, SCHEMAS)
    # the app stores them at startup, but tests seed users before it starts
    database.run(ensure_roles(database.database))
    yield database
    database.close()


@pytest.fixture
def db(api_database) -> Generator[SyncDatabase, Any, None]:
    """The app's database, emptied after the test"""
    from api.rest.database import SCHEMAS

    yield api_database
    # emptied, not dropped: the running app's tables and indexes stay, as do the roles
    # and notice templates it writes at startup
    for schema in reversed(SCHEMAS):
        if schema.__name__ not in _SCHEMAS_KEPT_ACROSS_TESTS:
            api_database.delete_many(schema, {})


@pytest.fixture
def request_log_db() -> redis.Redis:
    """The redis database of the request log for testing"""
    client = redis.Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    yield client
    # clean up
    client.flushdb()
    client.close()


@pytest.fixture(params=DATABASE_KINDS)
async def database_url(request, tmp_path) -> str:
    """The URL of a database, each kind in turn, emptied before and after the test"""
    database_url = get_database_url(request.param, tmp_path)
    await reset_database(database_url)
    yield database_url
    await reset_database(database_url)


@pytest.fixture(params=SQL_DATABASE_KINDS)
async def sql_database_url(request, tmp_path) -> str:
    """The URL of a SQL database, each kind in turn, with no tables left from other tests"""
    database_url = get_sql_database_url(request.param, tmp_path)
    await reset_sql_database(database_url)
    yield database_url
    await reset_sql_database(database_url)


@pytest.fixture(scope="session")
def app_runner(api_database) -> Generator["_AppRunner", Any, None]:
    """The app, started once for the whole session, as its startup is slow"""
    runner = _AppRunner()
    yield runner
    runner.stop()


@pytest.fixture
def client(
    request, app_runner, db, request_log_db, mock_socket_gethostbyname
) -> Generator[TestClient, Any, None]:
    """A test client for fast api, on the app the session keeps running

    A test that changes what the app starts with gets a client of its own, whose `with`
    block starts the app afresh.
    """
    from api.rest import app

    init_test_auth(db)
    if _FRESH_APP_FIXTURES & set(request.fixturenames):
        app_runner.stop()
        yield TestClient(app, follow_redirects=True)
        return

    running_client = app_runner.get_client()
    yield _RunningClient(running_client)
    running_client.cookies.clear()


@pytest.fixture
def mock_socket_gethostbyname(mocker):
    """Mock socket gethostbyname because 'testclient' is not a valid domain name"""
    from socket import gethostbyname as orig_gethostbyname

    def dummy_gethostbyname(hostname: str, /) -> str:
        if hostname in ("testclient",):
            return hostname
        return orig_gethostbyname(hostname)

    mocker.patch("socket.gethostbyname", side_effect=dummy_gethostbyname)
    yield mocker


@pytest.fixture
def app_token_header() -> Dict[str, str]:
    """the auth header for the client when app tokens are used"""
    yield {"Authorization": f"Bearer {TEST_APP_TOKEN_STRING}"}


@pytest.fixture
def current_user_id() -> Dict[str, str]:
    """the current user for the default app token"""
    yield TEST_USER_DICT["_id"]


@pytest.fixture
def no_qpu_app_token_header() -> Dict[str, str]:
    """the auth header for the client when the project has negative qpu seconds"""
    yield {"Authorization": f"Bearer {TEST_NO_QPU_APP_TOKEN_STRING}"}


@pytest.fixture
def system_app_token_header() -> Dict[str, str]:
    """the auth header for the client when the user is a system user"""
    yield {"Authorization": f"Bearer {TEST_SYSTEM_USER_APP_TOKEN_STRING}"}


@pytest.fixture
def user_jwt_cookie() -> Dict[str, str]:
    """the auth cookie for the client when JWT of user is used"""
    yield get_auth_cookie(TEST_USER_ID)


@pytest.fixture
def admin_jwt_cookie() -> Dict[str, str]:
    """the auth cookie for the client when JWT of an admin is used"""
    yield get_auth_cookie(TEST_SUPERUSER_ID)


@pytest.fixture
def system_user_jwt_cookie() -> Dict[str, str]:
    """the auth cookie of the system user, a member but not the admin of the test project"""
    yield get_auth_cookie(TEST_SYSTEM_USER_ID)


@pytest.fixture
def outsider_jwt_cookie() -> Dict[str, str]:
    """the auth cookie of a plain user who belongs to no project"""
    yield get_auth_cookie(TEST_OUTSIDER_ID)


@pytest.fixture
def project_id(db) -> Generator[str, Any, None]:
    """the project id for the default app token header"""
    yield TEST_PROJECT_ID


@pytest.fixture
def inserted_projects(db) -> Dict[str, Dict[str, Any]]:
    """A dictionary of inserted projects"""
    from services.auth import Project

    projects = {}
    for item in PROJECT_LIST:
        projects[item["_id"]] = {**item}
        insert_if_not_exist(db, Project, item)

    yield projects


@pytest.fixture
def inserted_project_ids(inserted_projects) -> List[str]:
    """A list of inserted project ids for version 2"""
    yield list(inserted_projects.keys())


@pytest.fixture
def personal_project(db) -> Generator[Dict[str, Any], Any, None]:
    """The personal project of the test user, as created on their login"""
    from services.auth import Project

    record = {
        "_id": derive_id(TEST_USER_ID, namespace="project"),
        "name": "john.doe (personal)",
        "description": "john.doe personal project",
        "admin_id": TEST_USER_ID,
        "user_ids": [TEST_USER_ID],
        "qpu_seconds": 0,
        "is_active": True,
        "is_personal": True,
        "created_at": "2024-09-20T09:12:00.733Z",
        "updated_at": "2024-09-20T09:12:00.733Z",
    }
    insert_if_not_exist(db, Project, record)
    yield record


@pytest.fixture
def unallocated_projects(db) -> Dict[str, Dict[str, Any]]:
    """A dictionary of project with qpu_seconds less or equal to zero"""
    from services.auth import Project

    projects = {}
    for item in PROJECT_LIST:
        qpu_seconds = int(random.uniform(-54000, 0))
        projects[item["_id"]] = {**item, "qpu_seconds": qpu_seconds}
        insert_if_not_exist(db, Project, {**item, "qpu_seconds": qpu_seconds})

    yield projects


@pytest.fixture
def app_tokens_with_timestamps(db) -> Generator[List[Dict[str, Any]], Any, None]:
    """A list of inserted app tokens"""
    from services.auth import AppToken

    tokens = []
    for item in APP_TOKEN_LIST:
        created_at = datetime.now(timezone.utc)

        # ensure you don't mutate the original item in APP_TOKEN_LIST
        tokens.append({**item, "created_at": created_at})
        db_item = {**item, "created_at": created_at}
        insert_if_not_exist(db, AppToken, db_item)

    yield tokens


@pytest.fixture
def inserted_app_tokens(db) -> Generator[List[Dict[str, Any]], Any, None]:
    """A list of inserted app tokens"""
    from services.auth import AppToken

    tokens = []
    for item in APP_TOKEN_LIST:
        # ensure you don't mutate the original item in APP_TOKEN_LIST
        tokens.append({**item})
        insert_if_not_exist(db, AppToken, item)

    yield tokens


@pytest.fixture
def inserted_notices(db) -> Generator[List[Dict[str, Any]], Any, None]:
    """A list of inserted notices, starting and expiring relative to now"""
    from services.notices import Notice

    records = with_offset_datetimes(
        [dict(item) for item in NOTICE_LIST],
        {
            "starts_at": "starts_at_offset_hours",
            "expires_at": "expires_at_offset_hours",
        },
    )
    for record in records:
        insert_if_not_exist(db, Notice, record)

    yield records


@pytest.fixture
def inserted_requests(db) -> Generator[List[Dict[str, Any]], Any, None]:
    """A list of inserted user requests"""
    from services.requests import Request

    records = [dict(item) for item in USER_REQUEST_LIST]
    for record in records:
        insert_if_not_exist(db, Request, record)

    yield records


@pytest.fixture(autouse=True)
def smtp(mocker):
    """Captures the emails handed to the SMTP server instead of sending them"""
    mocker.patch.object(aiosmtplib.SMTP, "connect", new_callable=mocker.AsyncMock)
    mocker.patch.object(aiosmtplib.SMTP, "quit", new_callable=mocker.AsyncMock)
    yield mocker.patch.object(
        aiosmtplib.SMTP, "send_message", new_callable=mocker.AsyncMock
    )


@pytest.fixture
def paused_email_sweeper(mocker):
    """Keeps the pending notice emails unswept, so their queueing can be checked alone"""
    yield mocker.patch(
        "services.notices.emails._find_notices_pending_email", return_value=[]
    )


@pytest.fixture
def unconfigured_email(mocker):
    """Runs the app without an [email] config, as if the table were omitted"""
    import settings

    yield mocker.patch.object(settings.CONFIG, "email", None)


class _AppRunner:
    """Keeps the app started across tests; stopped, it starts again when next asked"""

    def __init__(self):
        self._client: Optional[TestClient] = None

    def get_client(self) -> TestClient:
        if self._client is None:
            from api.rest import app

            self._client = TestClient(app, follow_redirects=True)
            self._client.__enter__()
        return self._client

    def stop(self) -> None:
        if self._client is not None:
            self._client.__exit__(None, None, None)
            self._client = None


class _RunningClient:
    """The running app's client, whose `with` block neither starts nor stops the app"""

    def __init__(self, client: TestClient):
        self._client = client

    def __enter__(self) -> TestClient:
        return self._client

    def __exit__(self, *exc_info) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)
