"""Data Transfer Objects for the auth providers"""

from fastapi import Query
from pydantic import BaseModel

from utils.models import create_partial_model


class AuthProviderRead(BaseModel):
    """The public view of an auth provider"""

    name: str
    url: str


class AuthProvider(AuthProviderRead):
    """The internal schema for all auth providers"""

    email_domain: str

    def as_public_view(self) -> AuthProviderRead:
        """Returns this instance as a AuthProviderRead instance"""
        return AuthProviderRead(
            name=self.name,
            url=self.url,
        )


# derived modela

AuthProviderQuery = create_partial_model(
    "AuthProviderQuery",
    original=AuthProvider,
    default=Query(None),
    exclude=("url",),
)
