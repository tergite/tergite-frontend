# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Utilities specific to auth when testing"""
from typing import Any, Dict, Optional, Type, TypeVar

import jwt
from beanie import Document, PydanticObjectId
from fastapi_users.jwt import decode_jwt, generate_jwt
from fastapi_users.password import PasswordHelper
from pymongo import ReturnDocument, collection, database, errors

from services.auth.app_tokens.dtos import AppToken
from services.auth.projects.dtos import Project
from services.auth.users.dtos import User
from tests._utils.env import TEST_JWT_SECRET
from utils.config import UserRole

TEST_PROJECT_ID = "bf4876d01e60f05ebc9fac9e"
TEST_NO_QPU_PROJECT_ID = "fd530427c7141f2693aa850b"
TEST_USER_ID = "8154077d9cb952b92453d575"
TEST_SUPERUSER_ID = "de7ddbd2500951be940356a2"
TEST_SYSTEM_USER_ID = "6431c4a4508205d9d43015fe"
TEST_OUTSIDER_ID = "9264188e0dc063ea3564e686"
TEST_USER_EMAIL = "john.doe@example.com"
TEST_OUTSIDER_EMAIL = "outsider.doe@example.com"
TEST_SUPERUSER_EMAIL = "jane.doe@example.com"
TEST_SYSTEM_USER_EMAIL = "system.doe@example.com"
TEST_APP_TOKEN_STRING = "46-0Jhgb1_thq8MqIF0SlVHoS8rFPiLBFL33XO_eJ7I"
TEST_NO_QPU_APP_TOKEN_STRING = "56-0Khgb1_thq8MyIF0Srtye8rFPiLBFL33XO_et7I"
TEST_SYSTEM_USER_APP_TOKEN_STRING = "l5ZPTt/AcD18ogpXhYfIYfmQTwc4tp917F3g708Uc1oAT0WW"

_password_helper = PasswordHelper()

TEST_GITHUB_PROFILE = dict(id="test-github-user", email="paul.doe@example.com")
INVALID_GITHUB_PROFILE = dict(id="invalid-github-user", email="julie.doe@example.com")

TEST_CHALMERS_PROFILE = dict(
    id="test-chalmers-user", userPrincipalName="paul.doe@chalmers.com"
)
INVALID_CHALMERS_PROFILE = dict(
    id="invalid-chalmers-user", userPrincipalName="paul.doe@chalmers.org"
)

TEST_GITHUB_TOKEN_RESP = {
    "access_token": "gho_16C7e42F292c6912E7710c838347Ae178B4a",
    "scope": "user,user:email",
    "token_type": "bearer",
}

TEST_CHALMERS_TOKEN_RESP = {
    "access_token": "gho_16C7e42F292c6912E7710c838347Ae178B4a",
    "scope": "User.Read",
    "token_type": "bearer",
}

TEST_PUHURI_TOKEN_RESP = {
    "access_token": "gho_16C7e42F292c6912E7710c838347Ae178B4a",
    "scope": "openid,email",
    "token_type": "bearer",
}


TEST_SUPERUSER_DICT = dict(
    _id=PydanticObjectId(TEST_SUPERUSER_ID),
    email=TEST_SUPERUSER_EMAIL,
    roles=[UserRole.USER, UserRole.ADMIN],
    hashed_password=_password_helper.hash(_password_helper.generate()),
    is_verified=True,
)
TEST_USER_DICT = dict(
    _id=PydanticObjectId(TEST_USER_ID),
    email=TEST_USER_EMAIL,
    roles=[UserRole.USER],
    hashed_password=_password_helper.hash(_password_helper.generate()),
    is_verified=True,
)
# a plain user who administers nothing and belongs to no project
TEST_OUTSIDER_DICT = dict(
    _id=PydanticObjectId(TEST_OUTSIDER_ID),
    email=TEST_OUTSIDER_EMAIL,
    roles=[UserRole.USER],
    hashed_password=_password_helper.hash(_password_helper.generate()),
    is_verified=True,
)
TEST_SYSTEM_USER_DICT = dict(
    _id=PydanticObjectId(TEST_SYSTEM_USER_ID),
    email=TEST_SYSTEM_USER_EMAIL,
    roles=[UserRole.SYSTEM],
    hashed_password=_password_helper.hash(_password_helper.generate()),
    is_verified=True,
)
USER_ID_EMAIL_MAP = {
    TEST_USER_ID: TEST_USER_EMAIL,
    TEST_OUTSIDER_ID: TEST_OUTSIDER_EMAIL,
    TEST_SUPERUSER_ID: TEST_SUPERUSER_EMAIL,
    TEST_SYSTEM_USER_ID: TEST_SYSTEM_USER_EMAIL,
}
TEST_PROJECT_NAME = "test-project"
TEST_PROJECT_DICT = dict(
    _id=PydanticObjectId(TEST_PROJECT_ID),
    name=TEST_PROJECT_NAME,
    description="some default project",
    admin_id=PydanticObjectId(TEST_USER_ID),
    user_ids=[PydanticObjectId(TEST_USER_ID), PydanticObjectId(TEST_SYSTEM_USER_ID)],
    qpu_seconds=108000000000000,
    created_at="2024-09-20T09:12:00.733Z",
    updated_at="2024-09-20T09:12:00.733Z",
)

TEST_NO_QPU_PROJECT_NAME = "test-no-qpu-project"
TEST_NO_QPU_PROJECT_DICT = dict(
    _id=PydanticObjectId(TEST_NO_QPU_PROJECT_ID),
    name=TEST_NO_QPU_PROJECT_NAME,
    description="some project without QPU seconds",
    admin_id=PydanticObjectId(TEST_USER_ID),
    user_ids=[PydanticObjectId(TEST_USER_ID)],
    qpu_seconds=-108000,
    created_at="2024-09-20T09:12:00.733Z",
    updated_at="2024-09-20T09:12:00.733Z",
)

TEST_APP_TOKEN_DICT = dict(
    title="test-token",
    token=TEST_APP_TOKEN_STRING,
    user_id=TEST_USER_DICT["_id"],
    project_id=TEST_PROJECT_DICT["_id"],
    lifespan_seconds=3600,
)

TEST_NO_QPU_APP_TOKEN_DICT = dict(
    title="no-qpu-token",
    token=TEST_NO_QPU_APP_TOKEN_STRING,
    user_id=TEST_USER_DICT["_id"],
    project_id=TEST_NO_QPU_PROJECT_DICT["_id"],
    lifespan_seconds=3600,
)

TEST_SYSTEM_USER_TOKEN_DICT = dict(
    title="system-user-token",
    token=TEST_SYSTEM_USER_APP_TOKEN_STRING,
    user_id=TEST_SYSTEM_USER_DICT["_id"],
    project_id=TEST_PROJECT_DICT["_id"],
    lifespan_seconds=3600,
)


def init_test_auth(db: database.Database):
    """Initializes the auth items in the test database in version 2"""
    insert_if_not_exist(db, User, TEST_USER_DICT)
    insert_if_not_exist(db, User, TEST_SUPERUSER_DICT)
    insert_if_not_exist(db, User, TEST_SYSTEM_USER_DICT)
    insert_if_not_exist(db, User, TEST_OUTSIDER_DICT)
    insert_if_not_exist(db, Project, TEST_PROJECT_DICT)
    insert_if_not_exist(db, Project, TEST_NO_QPU_PROJECT_DICT)
    insert_if_not_exist(db, AppToken, TEST_APP_TOKEN_DICT)
    insert_if_not_exist(db, AppToken, TEST_NO_QPU_APP_TOKEN_DICT)
    insert_if_not_exist(db, AppToken, TEST_SYSTEM_USER_TOKEN_DICT)


T = TypeVar("T", bound=Document)


def insert_if_not_exist(db: database.Database, schema: Type[T], data: Dict[str, Any]):
    """Inserts a given auth document into the database if it does not exist

    Args:
        db: The pymongo.database.Database instance to insert into
        schema: the beanie.Document schema corresponding to the collection to which to insert into
        data: the document to insert
    """
    try:
        col: collection.Collection = db[schema.Settings.name]
        col.insert_one(data)
    except errors.DuplicateKeyError:
        pass


def get_db_record(
    db: database.Database,
    schema: Type[T],
    _id: Optional[str] = None,
    _filter: Optional[dict] = None,
) -> Optional[dict]:
    """Gets a given auth document from the database or None if it does not exist"""
    col: collection.Collection = db[schema.Settings.name]
    filter_obj = {"_id": PydanticObjectId(_id)} if _id else {}
    if _filter is not None:
        filter_obj.update(_filter)
    return col.find_one(filter_obj)


def update_db_record(
    db: database.Database,
    schema: Type[T],
    _id: Optional[str] = None,
    _filter: Optional[dict] = None,
    update: Optional[dict] = None,
) -> Optional[dict]:
    """Updates the given auth document"""
    col: collection.Collection = db[schema.Settings.name]
    filter_obj = {"_id": PydanticObjectId(_id)} if _id else {}
    if _filter is not None:
        filter_obj.update(_filter)
    payload = update if isinstance(update, dict) else {}
    return col.find_one_and_update(
        filter_obj, payload, return_document=ReturnDocument.AFTER
    )


def get_jwt_token(
    user_id: str, ttl: int = 3600, secret: str = TEST_JWT_SECRET, **kwargs
) -> str:
    """Generates a valid JWT token for the given user_id"""
    data = {**kwargs, "sub": user_id, "aud": ["fastapi-users:auth"]}

    return generate_jwt(
        data=data, secret=secret, lifetime_seconds=ttl, algorithm="HS256"
    )


def get_auth_cookie(user_id: str) -> Dict[str, str]:
    """Generates the authorization cookie for the given user_id"""
    return {"some-cookie": get_jwt_token(user_id)}


def is_valid_jwt(token: str, secret: str = TEST_JWT_SECRET) -> bool:
    """Checks that the given JWT is a valid JWT

    Args:
        token: the JWT token to be checked
        secret: the JWT secret used to encode the JWT
    """
    audience = ["fastapi-users:auth"]
    algorithms = ["HS256"]

    try:
        data = decode_jwt(
            token, secret=secret, audience=audience, algorithms=algorithms
        )
        return "sub" in data
    except jwt.PyJWTError:
        return False
