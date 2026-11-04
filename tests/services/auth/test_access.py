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
"""The access rules app tokens are checked against, one row per outcome"""

from typing import Optional, Set, Type

import pytest

from libs.storage import generate_id
from services.auth import (
    LAX,
    STRICT,
    SYSTEM,
    AccessRule,
    Project,
    TokenOwner,
    User,
    check_project_access,
)
from utils.config import UserRole
from utils.exc import ForbiddenError, UnauthorizedError


@pytest.mark.parametrize(
    "rule, is_active, qpu_seconds, roles, error, message",
    [
        (STRICT, True, 10, {UserRole.USER}, None, None),
        (STRICT, False, 10, {UserRole.USER}, UnauthorizedError, "Unauthorized"),
        (
            STRICT,
            True,
            0,
            {UserRole.USER},
            ForbiddenError,
            "0.0 QPU seconds left on project p",
        ),
        (LAX, True, 0, {UserRole.USER}, None, None),
        (LAX, False, 10, {UserRole.USER}, UnauthorizedError, "Unauthorized"),
        (SYSTEM, True, 10, {UserRole.SYSTEM}, None, None),
        (SYSTEM, True, 10, {UserRole.USER}, ForbiddenError, "Forbidden"),
        (
            SYSTEM,
            True,
            -1,
            {UserRole.SYSTEM},
            ForbiddenError,
            "-1.0 QPU seconds left on project p",
        ),
    ],
)
def test_an_owner_passes_a_rule_only_with_what_it_needs(
    rule: AccessRule,
    is_active: bool,
    qpu_seconds: float,
    roles: Set[UserRole],
    error: Optional[Type[Exception]],
    message: Optional[str],
):
    owner = TokenOwner(
        project=Project(
            name="p",
            admin_id=generate_id(),
            user_ids=[],
            is_active=is_active,
            qpu_seconds=qpu_seconds,
        ),
        user=User.model_construct(roles=roles),
    )

    if error is None:
        assert check_project_access(owner, rule) is owner
    else:
        with pytest.raises(error) as caught:
            check_project_access(owner, rule)
        assert str(caught.value) == message


@pytest.mark.parametrize("rule", [STRICT, LAX, SYSTEM])
def test_an_inactive_user_is_unauthorized_under_every_rule(rule: AccessRule):
    owner = TokenOwner(
        project=Project(name="p", admin_id=generate_id(), user_ids=[], qpu_seconds=10),
        user=User.model_construct(roles={UserRole.SYSTEM}, is_active=False),
    )

    with pytest.raises(UnauthorizedError):
        check_project_access(owner, rule)


@pytest.mark.parametrize("rule", [STRICT, LAX, SYSTEM])
def test_a_missing_token_is_unauthorized_under_every_rule(rule: AccessRule):
    with pytest.raises(UnauthorizedError):
        check_project_access(None, rule)
