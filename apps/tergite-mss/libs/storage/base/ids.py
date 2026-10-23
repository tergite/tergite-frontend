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

"""Record ids: strings of 24 lowercase hex characters, ordered by creation time"""
import hashlib
from typing import Annotated, Any, Optional, Sequence, get_args, get_origin

from bson import ObjectId
from pydantic import StringConstraints
from pydantic.fields import FieldInfo


class IdMarker:
    """Marks a field as an Id, so that a store can turn it into its own key type"""


Id = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{24}$"), IdMarker()]


def generate_id() -> str:
    """Generates a new id, later than any generated before it in this second"""
    # bson's ObjectId is exactly this shape; nothing about it ties the id to MongoDB
    return str(ObjectId())


def derive_id(parent_id: str, namespace: str) -> str:
    """Computes an id from another: the same pair always gives the same id

    Args:
        parent_id: the id the new one is computed from
        namespace: separates the ids derived from one parent for different purposes

    Returns:
        the derived id
    """
    payload = f"{namespace}:{parent_id}".encode("utf-8")
    return hashlib.sha256(payload).digest()[:12].hex()


def is_id_field(field_info: Optional[FieldInfo]) -> bool:
    """Whether the field holds an Id, alone or in an Optional, List or Union"""
    if field_info is None:
        return False
    return _is_id_marker_in(field_info.metadata) or _is_id_inside(field_info.annotation)


def _is_id_inside(annotation: Any) -> bool:
    if _is_id_marker_in(getattr(annotation, "__metadata__", ())):
        return True
    return get_origin(annotation) is not None and any(
        _is_id_inside(arg) for arg in get_args(annotation)
    )


def _is_id_marker_in(metadata: Sequence[Any]) -> bool:
    return any(isinstance(item, IdMarker) for item in metadata)
