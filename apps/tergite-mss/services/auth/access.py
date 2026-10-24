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
"""Who may act on a project through an app token: the rules and their check"""
from dataclasses import dataclass
from typing import Optional, Tuple

from utils.config import UserRole
from utils.exc import ForbiddenError, UnauthorizedError

from .app_tokens.dtos import TokenOwner


@dataclass(frozen=True)
class AccessRule:
    """What a token's project and user must have for the token to pass"""

    is_qpu_required: bool
    roles: Tuple[UserRole, ...] = ()


STRICT = AccessRule(is_qpu_required=True)
LAX = AccessRule(is_qpu_required=False)
SYSTEM = AccessRule(is_qpu_required=True, roles=(UserRole.SYSTEM,))


def check_project_access(owner: Optional[TokenOwner], rule: AccessRule) -> TokenOwner:
    """Checks that the owner of an app token may act on its project under the rule

    Args:
        owner: the project and user of the app token; None for a missing or bad token
        rule: what the project and user must have

    Returns:
        the owner, once it passes

    Raises:
        UnauthorizedError: there is no owner or its project is inactive
        ForbiddenError: the rule needs QPU seconds the project lacks, or a role the user lacks
    """
    if owner is None or not owner.project.is_active:
        raise UnauthorizedError("Unauthorized")
    if rule.is_qpu_required and owner.project.qpu_seconds <= 0:
        raise ForbiddenError(
            f"{owner.project.qpu_seconds} QPU seconds left on project {owner.project.name}"
        )
    if rule.roles and owner.user.roles.isdisjoint(rule.roles):
        raise ForbiddenError("Forbidden")
    return owner
