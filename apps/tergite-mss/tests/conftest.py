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

from tests._utils.env import (
    TEST_DB_NAME,
    TEST_MONGODB_URL,
    setup_test_env,
)
from tests._utils.types import stub_pydantic_match_type_for_freezegun

# Set up the test environment before any other imports are made
setup_test_env()
# See: https://github.com/pydantic/pydantic/discussions/9343#discussioncomment-10723743
stub_pydantic_match_type_for_freezegun()

import settings
from utils.date_time import set_datetime_precision

# as the app does at startup, before any helper writes a timestamp
set_datetime_precision(settings.CONFIG.datetime_precision)

import random
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List

import aiosmtplib
import pymongo.database
import pytest
from beanie import PydanticObjectId
from fastapi.testclient import TestClient

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
from tests._utils.mongodb import (
    get_db_record,
    insert_if_not_exist,
)
from tests._utils.records import (
    get_app_token_record,
    get_notice_record,
    get_project_record,
    get_request_record,
    with_offset_datetimes,
)

BACKEND_SLUGS = ("Loke", "Pingu")
PROJECT_LIST = load_json_fixture("project_list.json")
APP_TOKEN_LIST = load_json_fixture("app_token_list.json")
NOTICE_LIST = load_json_fixture("notices.json")
USER_REQUEST_LIST = load_json_fixture("user_requests.json")
pytest_plugins = ["tests._utils.oauth", "tests._utils.mock_backend"]


@pytest.fixture
def db() -> pymongo.database.Database:
    """The mongo db instance for testing"""
    mongo_client = pymongo.MongoClient(TEST_MONGODB_URL)
    database = mongo_client[TEST_DB_NAME]

    yield database
    # clean up
    mongo_client.drop_database(TEST_DB_NAME)
    mongo_client.close()


@pytest.fixture
def client(db, mock_socket_gethostbyname) -> Generator[TestClient, Any, None]:
    """A test client for fast api"""
    from api.rest import app

    init_test_auth(db)
    yield TestClient(app, follow_redirects=True)


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
def project_id(db) -> Generator[PydanticObjectId, Any, None]:
    """the project id for the default app token header"""
    from services.auth import Project

    project = get_db_record(
        db, schema=Project, _filter={"_id": PydanticObjectId(TEST_PROJECT_ID)}
    )
    yield project["_id"]


@pytest.fixture
def inserted_projects(db) -> Dict[str, Dict[str, Any]]:
    """A dictionary of inserted projects"""
    from services.auth import Project

    projects = {}
    for item in PROJECT_LIST:
        projects[item["_id"]] = {**item}
        insert_if_not_exist(db, Project, get_project_record(item))

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
        "_id": PydanticObjectId(derive_id(TEST_USER_ID, namespace="project")),
        "name": "john.doe (personal)",
        "description": "john.doe personal project",
        "admin_id": PydanticObjectId(TEST_USER_ID),
        "user_ids": [PydanticObjectId(TEST_USER_ID)],
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
        insert_if_not_exist(
            db, Project, {**get_project_record(item), "qpu_seconds": qpu_seconds}
        )

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
        db_item = {**get_app_token_record(item), "created_at": created_at}
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
        insert_if_not_exist(db, AppToken, get_app_token_record(item))

    yield tokens


@pytest.fixture
def inserted_notices(db) -> Generator[List[Dict[str, Any]], Any, None]:
    """A list of inserted notices, starting and expiring relative to now"""
    from services.notices import Notice

    records = with_offset_datetimes(
        [get_notice_record(item) for item in NOTICE_LIST],
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

    records = [get_request_record(item) for item in USER_REQUEST_LIST]
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
