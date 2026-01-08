from tests._utils.env import (
    TEST_BACKENDS,
    TEST_DB_NAME,
    TEST_DISABLED_PUHURI_APP_CONFIG_JSON,
    TEST_JWT_SECRET,
    TEST_MONGODB_URL,
    TEST_PUHURI_CONFIG_ENDPOINT,
    setup_test_env,
)
from tests._utils.types import stub_pydantic_match_type_for_freezegun

# Set up the test environment before any other imports are made
setup_test_env()
# See: https://github.com/pydantic/pydantic/discussions/9343#discussioncomment-10723743
stub_pydantic_match_type_for_freezegun()

import importlib
import multiprocessing
import random
from datetime import datetime, timezone
from os import environ
from typing import Any, Dict, Generator, List
from unittest.mock import Mock

import httpx
import pymongo.database
import pytest
from beanie import PydanticObjectId
from fastapi.testclient import TestClient
from fastapi_users.router.oauth import generate_state_token
from filelock import FileLock
from httpx_oauth.clients import github, microsoft

import settings
from services.auth.projects.dtos import ProjectSource
from services.external import puhuri
from tests._utils import mock_backend
from tests._utils.auth import (
    INVALID_CHALMERS_PROFILE,
    INVALID_GITHUB_PROFILE,
    INVALID_PUHURI_PROFILE,
    TEST_APP_TOKEN_STRING,
    TEST_CHALMERS_PROFILE,
    TEST_CHALMERS_TOKEN_RESP,
    TEST_GITHUB_PROFILE,
    TEST_GITHUB_TOKEN_RESP,
    TEST_NO_QPU_APP_TOKEN_STRING,
    TEST_PROJECT_EXT_ID,
    TEST_PUHURI_PROFILE,
    TEST_PUHURI_TOKEN_RESP,
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
from tests._utils.waldur import MockWaldurClient

BACKEND_SLUGS = ("loke", "pingu")
_PUHURI_OPENID_CONFIG = load_json_fixture("puhuri_openid_config.json")
PROJECT_LIST = load_json_fixture("project_list.json")
APP_TOKEN_LIST = load_json_fixture("app_token_list.json")
JOB_LIST = load_json_fixture("job_list.json")
TEST_NEXT_COOKIE_URL = "https://testserver/"


@pytest.fixture
def mock_puhuri_synchronize(mocker) -> Mock:
    """A mock of the internal puhuri synchronize"""
    mocker.patch("services.external.puhuri.synchronize")
    yield puhuri.synchronize


@pytest.fixture
def disabled_puhuri_sync():
    """Disables PUHURI synchronization"""
    original_env = {
        "MSS_CONFIG_JSON_STR": environ.get("MSS_CONFIG_JSON_STR", ""),
    }

    environ["MSS_CONFIG_JSON_STR"] = TEST_DISABLED_PUHURI_APP_CONFIG_JSON
    importlib.reload(settings)
    yield

    # reset
    environ["MSS_CONFIG_JSON_STR"] = original_env["MSS_CONFIG_JSON_STR"]
    importlib.reload(settings)


@pytest.fixture
def mock_puhuri(respx_mock):
    """Mock of the puhuri openid config url"""
    respx_mock.get(TEST_PUHURI_CONFIG_ENDPOINT).mock(
        return_value=httpx.Response(status_code=200, json=_PUHURI_OPENID_CONFIG)
    )
    yield respx_mock


@pytest.fixture
def mock_puhuri_sync_calls():
    """A mock puhuri client that initializes the puhuri sync process"""
    # ensure that all processes in this case are 'spawn'ed regardless
    #   of operating system type
    with FileLock(".semaphore.lock"):
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        worker = ctx.Process(
            target=setup_puhuri_sync,
            args=([], queue),
        )
        worker.start()

        yield queue

        # clean up
        worker.terminate()
        worker.join()
        worker.close()


@pytest.fixture
def db(mock_puhuri) -> pymongo.database.Database:
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
def client(db) -> Generator[TestClient, Any, None]:
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
def existing_puhuri_projects(db) -> List[Dict[str, Any]]:
    """A list of pre-existing puhuri projects"""
    from services.auth import Project

    projects = []
    for item in PROJECT_LIST:
        record = {
            **item,
            "source": ProjectSource.PUHURI.value,
            "_id": PydanticObjectId(item["_id"]),
        }
        projects.append({**record})
        insert_if_not_exist(db, Project, record)

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
def app_tokens_with_timestamps(db) -> List[Dict[str, Any]]:
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
def inserted_app_tokens(db) -> List[Dict[str, Any]]:
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
def oauth_state() -> str:
    """The state to use to make oauth2 requests"""
    yield generate_state_token({}, secret=TEST_JWT_SECRET)


@pytest.fixture
def cookie_oauth_state() -> str:
    """The state to use to make oauth2 requests when using cookies"""
    yield generate_state_token({"next": TEST_NEXT_COOKIE_URL}, secret=TEST_JWT_SECRET)


@pytest.fixture
def puhuri_user(respx_mock):
    """A valid puhuri user with right email format"""
    respx_mock.get(_PUHURI_OPENID_CONFIG["userinfo_endpoint"]).mock(
        return_value=httpx.Response(status_code=200, json=TEST_PUHURI_PROFILE)
    )

    respx_mock.post(_PUHURI_OPENID_CONFIG["token_endpoint"]).mock(
        return_value=httpx.Response(status_code=200, json=TEST_PUHURI_TOKEN_RESP)
    )

    yield respx_mock


@pytest.fixture
def invalid_puhuri_user(respx_mock):
    """An invalid puhuri user with wrong email format"""
    respx_mock.get(_PUHURI_OPENID_CONFIG["userinfo_endpoint"]).mock(
        return_value=httpx.Response(status_code=200, json=INVALID_PUHURI_PROFILE)
    )

    respx_mock.post(_PUHURI_OPENID_CONFIG["token_endpoint"]).mock(
        return_value=httpx.Response(status_code=200, json=TEST_PUHURI_TOKEN_RESP)
    )

    yield respx_mock


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


def setup_puhuri_sync(
    args,
    queue: multiprocessing.Queue,
    **kwargs,
):
    """Sets up the puhuri sync worker ready for a different thread/process

    Args:
        args: the args to pass to puhuri_sync.main
        queue: a queue for sharing state across processes
        kwargs: the key-word arguments to pass to puhuri_sync.main
    """
    setup_test_env()
    remove_modules(["settings", "api", "utils", "tests", "waldur_client", "services"])
    import waldur_client

    waldur_client.WaldurClient = lambda api_url, access_token: MockWaldurClient(
        api_url=api_url, access_token=access_token, queue=queue
    )

    from api.scripts import puhuri_sync

    puhuri_sync.main(args, **kwargs)
