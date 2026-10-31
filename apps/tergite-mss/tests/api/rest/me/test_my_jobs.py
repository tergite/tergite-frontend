# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2024, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import List, Optional

import pytest
from beanie import PydanticObjectId
from pytest_lazyfixture import lazy_fixture

from tests._utils.auth import TEST_SUPERUSER_ID, TEST_USER_ID
from tests._utils.fixtures import load_json_fixture
from tests._utils.mongodb import insert_in_collection
from tests._utils.records import filter_by_equality, order_by_many

_USER_ID_COOKIES_FIXTURE = [
    (TEST_USER_ID, lazy_fixture("user_jwt_cookie")),
    (TEST_SUPERUSER_ID, lazy_fixture("admin_jwt_cookie")),
]
_JOBS_COLLECTION = "jobs"
_SKIP_LIMIT_SORT_PARAMS = [
    (0, 1, ["-job_id", "created_at"]),
    (1, 4, None),
    (2, None, ["created_at"]),
]
_SEARCH_PARAMS = [
    {"device": "Loke"},
    {"device": "Pingu", "status": "successful"},
    {"status": "failed"},
    {},
    {"project_id": "653a8f19e736d76276597a6c"},
    {"project_id": "653a8f19e736d76276597a6c", "status": "pending"},
]
_PAGINATE_AND_SEARCH_PARAMS = [
    (skip, limit, sort, search, user_id, cookie)
    for skip, limit, sort in _SKIP_LIMIT_SORT_PARAMS
    for search in _SEARCH_PARAMS
    for user_id, cookie in _USER_ID_COOKIES_FIXTURE
]
_JOBS_LIST_IN_DB = [
    {
        **item,
        **{
            k: PydanticObjectId(item[k]) for k in ("project_id", "user_id") if k in item
        },
    }
    for item in load_json_fixture("my_jobs_in_db.json")
]
_JOBS_LIST_AS_RESPONSES = load_json_fixture("my_job_responses.json")


@pytest.mark.parametrize(
    "skip, limit, sort, search, user_id, cookies", _PAGINATE_AND_SEARCH_PARAMS
)
def test_find_my_jobs(
    db,
    client,
    skip: Optional[int],
    limit: Optional[int],
    sort: Optional[List[str]],
    search: dict,
    user_id,
    cookies,
):
    """Get to /me/job/?project_id=...&device=... can search for the jobs that fulfill the given filters"""
    insert_in_collection(
        database=db, collection_name=_JOBS_COLLECTION, data=_JOBS_LIST_IN_DB
    )

    query_string = "?"
    slice_end = len(_JOBS_LIST_IN_DB)
    slice_start = 0
    sort_fields = [
        "-created_at",
    ]
    if limit is not None:
        query_string += f"limit={limit}&"
        slice_end = limit
    if skip is not None:
        query_string += f"skip={skip}&"
        slice_start = skip
        slice_end += skip
    if sort is not None:
        sort_fields = sort
        for sort_field in sort_fields:
            query_string += f"sort={sort_field}&"

    # Adding search
    for key, value in search.items():
        query_string += f"{key}={value}&"

    # using context manager to ensure on_startup runs
    with client as client:
        response = client.get(f"/me/jobs/{query_string}", cookies=cookies)
        got = response.json()
        effective_filters = {**search, "user_id": user_id}
        filtered_data = filter_by_equality(
            _JOBS_LIST_AS_RESPONSES, filters=effective_filters
        )
        sorted_data = order_by_many(filtered_data, fields=sort_fields)
        expected = {
            "skip": slice_start,
            "limit": limit,
            "data": sorted_data[slice_start:slice_end],
        }

        assert response.status_code == 200
        assert got == expected
