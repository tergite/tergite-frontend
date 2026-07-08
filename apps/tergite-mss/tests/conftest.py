import redis
from redis import Redis

from tests._utils.env import (
    TEST_BACKENDS,
    TEST_DB_NAME,
    TEST_JWT_SECRET,
    TEST_MONGODB_URL,
    TEST_REDIS_URL,
    setup_test_env,
)
from tests._utils.types import stub_pydantic_match_type_for_freezegun

# Set up the test environment before any other imports are made
setup_test_env()
# See: https://github.com/pydantic/pydantic/discussions/9343#discussioncomment-10723743
stub_pydantic_match_type_for_freezegun()

import multiprocessing
import random
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List

import httpx
import pymongo.database
import pytest
from beanie import PydanticObjectId
from fastapi.testclient import TestClient
from fastapi_users.router.oauth import generate_state_token
from httpx_oauth.clients import github, microsoft

from services.auth.projects.dtos import ProjectSource
from tests._utils import mock_backend
from tests._utils.auth import (
    INVALID_CHALMERS_PROFILE,
    INVALID_GITHUB_PROFILE,
    TEST_APP_TOKEN_STRING,
    TEST_CHALMERS_PROFILE,
    TEST_CHALMERS_TOKEN_RESP,
    TEST_GITHUB_PROFILE,
    TEST_GITHUB_TOKEN_RESP,
    TEST_NO_QPU_APP_TOKEN_STRING,
    TEST_PROJECT_EXT_ID,
    TEST_SUPERUSER_ID,
    TEST_SYSTEM_USER_APP_TOKEN_STRING,
    TEST_USER_DICT,
    TEST_USER_ID,
    get_db_record,
    get_jwt_token,
    init_test_auth,
    insert_if_not_exist,
)
from tests._utils.fixtures import load_json_fixture
from tests._utils.mock_backend import CREATED_BOOKINGS
from tests._utils.modules import remove_modules

BACKEND_SLUGS = ("Loke", "Pingu")
PROJECT_LIST = load_json_fixture("project_list.json")
APP_TOKEN_LIST = load_json_fixture("app_token_list.json")
JOB_LIST = load_json_fixture("job_list.json")
TEST_NEXT_COOKIE_URL = "https://testserver/"
_redis_connection = redis.Redis.from_url(TEST_REDIS_URL)


@pytest.fixture
def redis_client() -> Generator[Redis, Any, None]:
    """A mock redis client"""
    yield _redis_connection
    _redis_connection.flushall()


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
def db() -> pymongo.database.Database:
    """The mongo db instance for testing"""
    mongo_client = pymongo.MongoClient(TEST_MONGODB_URL)
    database = mongo_client[TEST_DB_NAME]

    yield database
    # clean up
    mongo_client.drop_database(TEST_DB_NAME)
    mongo_client.close()


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
def user_jwt_header() -> Dict[str, str]:
    """the auth header for the client when JWT of user is used"""
    yield get_auth_header(TEST_USER_ID)


@pytest.fixture
def admin_jwt_header() -> Dict[str, str]:
    """the auth header for the client when JWT of an admin is used"""
    yield get_auth_header(TEST_SUPERUSER_ID)


@pytest.fixture
def user_jwt_cookie() -> Dict[str, str]:
    """the auth cookie for the client when JWT of user is used"""
    yield get_auth_cookie(TEST_USER_ID)


@pytest.fixture
def admin_jwt_cookie() -> Dict[str, str]:
    """the auth cookie for the client when JWT of an admin is used"""
    yield get_auth_cookie(TEST_SUPERUSER_ID)


@pytest.fixture
def project_id(db) -> PydanticObjectId:
    """the project id for the default app token header"""
    from services.auth import Project

    project = get_db_record(db, schema=Project, _filter={"ext_id": TEST_PROJECT_EXT_ID})
    yield project["_id"]


@pytest.fixture
def client(db, mock_socket_gethostbyname) -> Generator[TestClient, Any, None]:
    """A test client for fast api"""
    from api.rest import app

    init_test_auth(db)
    yield TestClient(app, follow_redirects=True)


@pytest.fixture
def inserted_projects(db) -> Dict[str, Dict[str, Any]]:
    """A dictionary of inserted projects"""
    from services.auth import Project

    projects = {}
    for item in PROJECT_LIST:
        projects[item["_id"]] = {**item}
        insert_if_not_exist(db, Project, {**item, "_id": PydanticObjectId(item["_id"])})

    yield projects


@pytest.fixture
def inserted_project_ids(inserted_projects) -> List[str]:
    """A list of inserted project ids for version 2"""
    yield list(inserted_projects.keys())


@pytest.fixture
def unallocated_projects(db) -> Dict[str, Dict[str, Any]]:
    """A dictionary of project with qpu_seconds less or equal to zero"""
    from services.auth import Project

    projects = {}
    for item in PROJECT_LIST:
        qpu_seconds = int(random.uniform(-54000, 0))
        projects[item["ext_id"]] = {**item, "qpu_seconds": qpu_seconds}
        insert_if_not_exist(
            db,
            Project,
            {**item, "_id": PydanticObjectId(item["_id"]), "qpu_seconds": qpu_seconds},
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
        db_item = {
            **item,
            "_id": PydanticObjectId(item["_id"]),
            "user_id": PydanticObjectId(item["user_id"]),
            "created_at": created_at,
        }
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
        db_item = {
            **item,
            "_id": PydanticObjectId(item["_id"]),
            "user_id": PydanticObjectId(item["user_id"]),
        }
        insert_if_not_exist(db, AppToken, db_item)

    yield tokens


@pytest.fixture
def oauth_state() -> Generator[str, Any, None]:
    """The state to use to make oauth2 requests"""
    yield generate_state_token({}, secret=TEST_JWT_SECRET)


@pytest.fixture
def cookie_oauth_state() -> Generator[str, Any, None]:
    """The state to use to make oauth2 requests when using cookies"""
    yield generate_state_token({"next": TEST_NEXT_COOKIE_URL}, secret=TEST_JWT_SECRET)


@pytest.fixture
def github_user(respx_mock):
    """A valid admin user with right email format"""
    respx_mock.get(github.PROFILE_ENDPOINT).mock(
        return_value=httpx.Response(status_code=200, json=TEST_GITHUB_PROFILE)
    )

    respx_mock.post(github.ACCESS_TOKEN_ENDPOINT).mock(
        return_value=httpx.Response(status_code=200, json=TEST_GITHUB_TOKEN_RESP)
    )

    yield respx_mock


@pytest.fixture
def invalid_github_user(respx_mock):
    """An invalid admin user with wrong email format"""
    respx_mock.get(github.PROFILE_ENDPOINT).mock(
        return_value=httpx.Response(status_code=200, json=INVALID_GITHUB_PROFILE)
    )

    respx_mock.post(github.ACCESS_TOKEN_ENDPOINT).mock(
        return_value=httpx.Response(status_code=200, json=TEST_GITHUB_TOKEN_RESP)
    )

    yield respx_mock


@pytest.fixture
def chalmers_user(respx_mock):
    """A valid Chalmers' user with right email format"""
    respx_mock.get(microsoft.PROFILE_ENDPOINT).mock(
        return_value=httpx.Response(status_code=200, json=TEST_CHALMERS_PROFILE)
    )

    access_token_url = microsoft.ACCESS_TOKEN_ENDPOINT.format(tenant="common")
    respx_mock.post(access_token_url).mock(
        return_value=httpx.Response(status_code=200, json=TEST_CHALMERS_TOKEN_RESP)
    )

    yield respx_mock


@pytest.fixture
def invalid_chalmers_user(respx_mock):
    """An invalid Chalmers' user with wrong email format"""
    respx_mock.get(microsoft.PROFILE_ENDPOINT).mock(
        return_value=httpx.Response(status_code=200, json=INVALID_CHALMERS_PROFILE)
    )

    access_token_url = microsoft.ACCESS_TOKEN_ENDPOINT.format(tenant="common")
    respx_mock.post(access_token_url).mock(
        return_value=httpx.Response(status_code=200, json=TEST_CHALMERS_TOKEN_RESP)
    )

    yield respx_mock


@pytest.fixture
def mock_bcc(respx_mock):
    """A mock BCC service"""
    for backend in TEST_BACKENDS:
        respx_mock.post(f"{backend['url']}/token").mock(
            side_effect=mock_backend.get_token
        )

        # users
        respx_mock.post(f"{backend['url']}/users").mock(
            side_effect=mock_backend.create_user
        )

        respx_mock.get(f"{backend['url']}/users").mock(
            side_effect=mock_backend.view_users
        )

        respx_mock.delete(f"{backend['url']}/users/USER_ID_PLACEHOLDER").mock(
            side_effect=mock_backend.delete_users
        )

        # bookings
        respx_mock.post(f"{backend['url']}/bookings").mock(
            side_effect=mock_backend.create_booking
        )

        respx_mock.get(f"{backend['url']}/bookings").mock(
            side_effect=mock_backend.view_bookings
        )

        respx_mock.get(f"{backend['url']}/bookings/config").mock(
            side_effect=mock_backend.view_bookings_config
        )

        for booking in CREATED_BOOKINGS:
            respx_mock.post(f"{backend['url']}/bookings/{booking['id']}/cancel").mock(
                side_effect=mock_backend.cancel_booking
            )

        # jobs
        for job in JOB_LIST:
            respx_mock.post(f"{backend['url']}/jobs/{job['job_id']}/cancel").mock(
                side_effect=mock_backend.cancel_job
            )

            respx_mock.delete(f"{backend['url']}/jobs/{job['job_id']}").mock(
                side_effect=mock_backend.delete_job
            )

        # recalibration
        respx_mock.post(f"{backend['url']}/recalibration/init").mock(
            side_effect=mock_backend.init_recalibration
        )

        respx_mock.get(f"{backend['url']}/recalibration/info").mock(
            side_effect=mock_backend.get_recalibration_info
        )

        respx_mock.post(f"{backend['url']}/recalibration/cancel").mock(
            side_effect=mock_backend.cancel_recalibration
        )

        # switch off
        respx_mock.post(f"{backend['url']}/switch/off").mock(
            side_effect=mock_backend.switch_off
        )

        respx_mock.post(f"{backend['url']}/switch/on").mock(
            side_effect=mock_backend.switch_on
        )

    yield respx_mock


@pytest.fixture
def mock_unavailable_bcc(respx_mock):
    """A mock BCC service that is unavailable"""
    for backend in TEST_BACKENDS:
        respx_mock.post(f"{backend['url']}/token").mock(side_effect=httpx.ConnectError)

    yield respx_mock


@pytest.fixture
def mock_timed_out_bcc(respx_mock):
    """A mock BCC service that times out"""
    for backend in TEST_BACKENDS:
        respx_mock.post(f"{backend['url']}/token").mock(
            side_effect=httpx.ConnectTimeout
        )

    yield respx_mock


def get_auth_header(user_id: str) -> Dict[str, Any]:
    """Retrieves the authorization header for the given user_id"""
    return {"Authorization": f"Bearer {get_jwt_token(user_id)}"}


def get_auth_cookie(user_id: str) -> Dict[str, str]:
    """Retrieves the authorization cookie for the given user_id"""
    return {"some-cookie": get_jwt_token(user_id)}


def get_unauthorized_app_token_post():
    """Returns the body and headers for unauthorized app token generation POST

    The auth header provided is for a user who does not have access
    to the given project
    """
    admin_only_projects = [
        project["ext_id"]
        for project in PROJECT_LIST
        if project["user_emails"] == [TEST_SUPERUSER_ID]
    ]

    user_only_projects = [
        project["ext_id"]
        for project in PROJECT_LIST
        if project["user_ids"] == [TEST_USER_ID]
    ]

    admin_only_post_data = [
        (body, get_auth_header(TEST_USER_ID))
        for body in APP_TOKEN_LIST
        if body["project_ext_id"] in admin_only_projects
    ]

    user_only_post_data = [
        (body, get_auth_header(TEST_SUPERUSER_ID))
        for body in APP_TOKEN_LIST
        if body["project_ext_id"] in user_only_projects
    ]

    return admin_only_post_data + user_only_post_data


def get_unauthorized_app_token_post_with_cookies():
    """Returns the body and cookies for unauthorized app token generation POST

    The auth cookie provided is for a user who does not have access
    to the given project
    """
    admin_only_projects = [
        project["ext_id"]
        for project in PROJECT_LIST
        if project["user_ids"] == [TEST_SUPERUSER_ID]
    ]

    user_only_projects = [
        project["ext_id"]
        for project in PROJECT_LIST
        if project["user_ids"] == [TEST_USER_ID]
    ]

    admin_only_post_data = [
        (body, get_auth_cookie(TEST_USER_ID))
        for body in APP_TOKEN_LIST
        if body["project_ext_id"] in admin_only_projects
    ]

    user_only_post_data = [
        (body, get_auth_cookie(TEST_SUPERUSER_ID))
        for body in APP_TOKEN_LIST
        if body["project_ext_id"] in user_only_projects
    ]

    return admin_only_post_data + user_only_post_data
