# This code is part of Tergite
#
# (C) Copyright François Voron 2019 (fastapi-users 14.0.2, MIT licence; see libs/authlib/LICENSE)
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr
from pydantic.version import VERSION as PYDANTIC_VERSION

from libs.authlib import models

PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

SCHEMA = TypeVar("SCHEMA", bound=BaseModel)

if PYDANTIC_V2:  # pragma: no cover

    def model_dump(model: BaseModel, *args, **kwargs) -> dict[str, Any]:
        return model.model_dump(*args, **kwargs)  # type: ignore

    def model_validate(schema: type[SCHEMA], obj: Any, *args, **kwargs) -> SCHEMA:
        return schema.model_validate(obj, *args, **kwargs)  # type: ignore

else:  # pragma: no cover  # type: ignore

    def model_dump(model: BaseModel, *args, **kwargs) -> dict[str, Any]:
        return model.dict(*args, **kwargs)  # type: ignore

    def model_validate(schema: type[SCHEMA], obj: Any, *args, **kwargs) -> SCHEMA:
        return schema.from_orm(obj)  # type: ignore


class BaseUser(BaseModel, Generic[models.ID]):
    """Base User model."""

    id: models.ID
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False

    if PYDANTIC_V2:  # pragma: no cover
        model_config = ConfigDict(from_attributes=True)  # type: ignore
    else:  # pragma: no cover

        class Config:
            orm_mode = True


U = TypeVar("U", bound=BaseUser)


class BaseOAuthAccount(BaseModel, Generic[models.ID]):
    """Base OAuth account model."""

    id: models.ID
    oauth_name: str
    access_token: str
    expires_at: Optional[int] = None
    refresh_token: Optional[str] = None
    account_id: str
    account_email: str

    if PYDANTIC_V2:  # pragma: no cover
        model_config = ConfigDict(from_attributes=True)  # type: ignore
    else:  # pragma: no cover

        class Config:
            orm_mode = True


class BaseOAuthAccountMixin(BaseModel):
    """Adds OAuth accounts list to a User model."""

    oauth_accounts: list[BaseOAuthAccount] = []
