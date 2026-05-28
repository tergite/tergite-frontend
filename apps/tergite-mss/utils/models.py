# This code is part of Tergite
#
# (C) Copyright Simon Genne, Arvid Holmqvist, Bashar Oumari, Jakob Ristner,
#               Björn Rosengren, and Jakob Wik 2022 (BSc project)
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
#
# Refactored by Martin Ahindura 2023-11-08
"""Utilities specific to models"""
import sys
from typing import (
    Any,
    Callable,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
    get_args,
)

from pydantic import BaseModel, ConfigDict, ValidationError, create_model
from pydantic.main import IncEx

from utils.exc import DbValidationError

ModelOrDict = TypeVar("ModelOrDict", dict, BaseModel)
Model = TypeVar("Model", bound=BaseModel)


class PartialMeta(BaseModel):
    """The base model for partial models that have all fields as optional"""

    model_config = ConfigDict(extra="ignore")

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        exclude_unset: bool = True,
        exclude_defaults: bool = True,
        exclude_none: bool = True,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        fallback: Callable[[Any], Any] | None = None,
        serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            fallback=fallback,
            serialize_as_any=serialize_as_any,
        )


def parse_record(type__: Type[ModelOrDict], record: Mapping[str, Any]) -> ModelOrDict:
    """Converts a record to the given type

    Args:
        type__: the type to parse to
        record: the item to convert

    Returns:
        the record converted to the given type

    Raises:
        ValidationError: the record has some pydantic validation errors
    """
    try:
        return type__.model_validate(record)
    except AttributeError:
        return dict(record)
    except ValidationError as exp:
        raise DbValidationError(exp)


def try_parse_record(
    type__: Type[ModelOrDict], record: Mapping[str, Any]
) -> Optional[ModelOrDict]:
    """Tries to convert the given record into the given type and returns None if it fails

    Args:
        type__: the type to parse to
        record: the item to convert

    Returns:
        the record converted to the given type or None if there were validation errors
    """
    try:
        return parse_record(type__, record)
    except DbValidationError:
        return None


def create_partial_model(
    name: str, original: type[Model], exclude: Sequence[str] = (), default: Any = None
) -> type[Model]:
    """Creates a model that has all its fields as optional based on the original

    Args:
        name: the name of the new model
        original: the original model whose fields are to be passed in as query params
        exclude: the fields of the original to exclude
        default: the default value of the fields

    Returns:
        the model to be used in the router
    """
    # make all fields optional so that the query parameters are optional
    fields = {
        name: (_as_optional(field.annotation), default)
        for name, field in original.model_fields.items()
        if name not in exclude
    }

    return create_model(
        name,
        # module of the calling function
        __module__=sys._getframe(1).f_globals["__name__"],
        __doc__=f"{PartialMeta.__doc__}\n\nOriginal:\n{original.__doc__}",
        __base__=(PartialMeta,),
        **fields,
    )


def _as_optional(type__) -> type:
    """Converts the type into an optional type if it was not one already

    Args:
        type__: the type to convert

    Returns:
        The type as an optional type
    """
    if type(None) in get_args(type__):
        return type__
    return Optional[type__]
