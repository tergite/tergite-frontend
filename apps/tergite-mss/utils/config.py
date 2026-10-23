# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Utility for loading configurations for the app"""

import enum
import json
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosmtplib
from pydantic import (
    AnyHttpUrl,
    AnyUrl,
    BaseModel,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

_PROJECT_FOLDER = Path(__file__).parent.parent


class DatetimePrecision(str, enum.Enum):
    """Possible datetime precision values: additional components of the time to include when isoformat is called

    See https://docs.python.org/3/library/datetime.html#datetime.datetime.isoformat
    """

    MILLISECONDS = "milliseconds"
    AUTO = "auto"
    MICROSECONDS = "microseconds"
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"


class DatabaseConfig(BaseModel):
    """Configuration for the database"""

    name: str
    # any URL a storage backend supports, e.g. mongodb://host:27017
    url: AnyUrl
    # the database of the request log, read and written on every request, so a cache
    # suits it; default=redis://tergite-redis:6379/0
    redis_url: AnyUrl = "redis://tergite-redis:6379/0"


class BccConfig(BaseModel):
    """Configuration for a single instance of BCC"""

    # the name of the backend computer that will be accessible from tergite.qiskit and from webGUI
    name: str
    # the URL where this backend is running
    url: AnyHttpUrl = "http://127.0.0.1:8002"
    # request timeout in seconds beyond which a timeout error is raised; default = 10
    timeout: int = 10
    # path to the public key of this backend
    public_key_path: Path
    # the URL to access this BCC publicly
    public_url: AnyHttpUrl = None
    # whether to ignore websocket's IP address check
    is_strict_ip: bool = True

    @field_validator("public_key_path", mode="before")
    @classmethod
    def validate_public_key_path(cls, v: Any):
        """Validate the public key path to ensure all relative paths are relative to the app root"""
        try:
            value_path = Path(v)
            if not value_path.is_absolute():
                return _PROJECT_FOLDER / value_path
            return value_path
        except TypeError:
            raise ValueError("public_key_path must be a Path or str")

    @model_validator(mode="before")
    @classmethod
    def set_public_url_if_none(cls, data: Any) -> Any:
        """Sets the public URL to the value of URL if public URL is none"""
        if isinstance(data, dict):
            if "public_url" not in data:
                data["public_url"] = data["url"]
        return data

    @computed_field
    @property
    def ip_address(self) -> str:
        """The IP address of the server where the device is"""
        return get_ip_addr(self.url.host)


class UserRole(str, enum.Enum):
    """The possible roles a user can have"""

    USER = "user"
    RESEARCHER = "researcher"
    ADMIN = "admin"
    PARTNER = "partner"
    SYSTEM = "system"


class Oauth2ClientType(str, enum.Enum):
    """The Oauth2 client type"""

    MICROSOFT = "microsoft"
    GITHUB = "github"
    GOOGLE = "google"
    OPENID = "openid"
    OKTA = "okta"


class Oauth2ClientConfig(BaseModel, extra="allow"):
    """The configuration for an Oauth2 Client i.e. a BaseOAuth2 instance

    This config allows other arbitrary properties to be added due to the use of Extra=allow
    """

    # Note that for Oauth2, you need an external Oauth2 provider like Github, Google, Chalmers, Puhuri etc.
    # You must thus register an app with that provider and in return, they should give you
    # a client_id, client_secret and optionally if using OpenID Connect, an openid_configuration_endpoint
    # For GitHub, see https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps
    # For microsoft, see https://learn.microsoft.com/en-us/azure/active-directory/develop/quickstart-web-app-python-sign-in?tabs=windows
    client_id: str
    client_secret: str

    # name as will appear in url qal9000.se/auth/{name}/ e.g. 'github' as in qal9000.se/auth/github/
    name: str
    openid_configuration_endpoint: Optional[str] = None

    # There are a couple of client types basing on the User Management software used by the company
    # e.g. many companies manage their users using microsoft active directory, other use GSuite, others Okta
    # and others just use OpenID connect to handle their authentication
    # The possible client_types include: 'microsoft', 'google', 'github', 'okta', 'openid'.
    # Note the spelling and the case.
    client_type: Oauth2ClientType

    # The callback URL that the Oauth2 provider should redirect to after authentication.
    # THIS IS A URL ON THIS APPLICATION and it is usually of the form:
    # https://example.com/auth/{name-of-client-e.g.-github}/callback
    redirect_url: str

    # the Regular expression for the emails that are allowed to sign into this application
    # using this Oauth2 method. For example, if I set up a GitHub client, I may not want every GitHub user
    # to access this application so I use "^(john\\.doe|jane|aggrey)@example\\.com$"
    # to allow only john.doe@example.com, jane@example.com and aggrey@example.com to login via this method
    # default = ".*"
    email_regex: str = ".*"

    # the domain of the emails of the users that should be directed to this auth client
    email_domain: str

    # The set of roles every user who logs in via this method should get.
    # Possible roles include: "admin", "user", "researcher", "partner". Default is 'user'
    roles: List[UserRole] = [UserRole.USER]

    # Whether the user should be associated with an existing user of the same email if
    # that user exists.
    # If False, a user who already signed in with a different Oauth provider will
    # not be allowed to sign in
    associate_by_email: bool = False

    # Whether when a user signs in, they are considered verified
    is_verified_by_default: bool = True

    # config fields that are not used to create the client
    _non_client_fields = {
        "client_type",
        "redirect_url",
        "email_regex",
        "roles",
        "email_domain",
        "associate_by_email",
        "is_verified_by_default",
    }


class ProjectsConfig(BaseModel):
    """Configuration for projects, including auto-created personal projects"""

    # QPU seconds a personal project is created with. Default 0 keeps an unconfigured
    # deployment behaving as it did before personal projects existed.
    personal_qpu_seconds: float = 0

    # notify the project admin when remaining QPU seconds fall below this
    qpu_seconds_low_threshold: float = 600


class EmailConfig(BaseModel):
    """SMTP settings. Omit the whole table to disable the email channel."""

    hostname: str = "localhost"
    port: int = 587
    username: str | bytes | None = None
    password: str | bytes | None = None
    timeout: float | None = aiosmtplib.smtp.DEFAULT_TIMEOUT
    use_tls: bool = False
    start_tls: bool | None = True

    from_address: str
    from_name: str = "Tergite"

    # A helper protected property to help during initialization of the email SMTP
    _non_smtp_fields = {
        "from_address",
        "from_name",
    }

    @property
    def non_smtp_fields(self) -> set[str]:
        """The fields that are not used when initializing the SMTP instance"""
        return self._non_smtp_fields


class NoticesConfig(BaseModel):
    """Configuration for the notices service"""

    # days a notification is kept before the TTL index removes it
    retention_days: int = Field(default=90, ge=0)

    # base URL of the dashboard, used for deep links in emails.
    dashboard_url: str = ""

    # seconds between outbox sweeps
    email_sweep_interval: float = Field(default=60, gt=0)

    # attempts before an email is marked failed
    email_retry_limit: int = Field(default=3, ge=0)

    # the name of the application as will be seen in the email notices
    app_name: str = "Tergite"


class AuthConfig(BaseModel):
    """Configration for auth"""

    # Secret for signing JWT tokens. https://jwt.io/introduction
    jwt_secret: str = "some hidden secret"

    # Time-to-live for the JWT tokens created by this app, default=3600
    jwt_ttl: int = 3600

    # domain to be set in the cookie, to limit its use to only that domain.
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies
    cookie_domain: str = ""

    # name of the cookie to be used when authenticating' default=tergiteauth
    cookie_name: str = "tergiteauth"

    # list of Oauth2 client config
    clients: List[Oauth2ClientConfig] = []


class AppConfig(BaseModel, extra="allow"):
    """Configuration for the entire app"""

    mss_port: int = 8002
    # environment reflect which environment the app is to run in.
    # Options
    #  - development
    #  - production
    #  - staging
    #  - test
    # Default: production
    environment: str = "production"

    # For datetime precisions; number of additional components of the time to include
    # See https://docs.python.org/3/library/datetime.html#datetime.datetime.isoformat
    # <any of 'milliseconds', 'auto', 'microseconds', 'seconds', 'minutes', 'hours'>; default = auto
    datetime_precision: DatetimePrecision = DatetimePrecision.AUTO

    # time-to-live for the nonce; defaults to 5 minutes
    bcc_nonce_ttl: float = 300

    # how long, in seconds, a request id or websocket nonce is remembered to reject a replay
    # default: 1209600 (two weeks)
    request_log_ttl: float = 1209600

    # configuration for one database; it might become possible to add multiple databases
    database: DatabaseConfig

    # the BCC instances connected to this MSS instance
    backends: List[BccConfig]

    # configuration for authentication
    auth: AuthConfig

    # configuration for projects and personal projects
    projects: ProjectsConfig = ProjectsConfig()

    # configuration for notices
    notices: NoticesConfig = NoticesConfig()

    # SMTP settings; None disables the email channel entirely
    email: Optional[EmailConfig] = None

    # cache for the backends dict
    _backends_dict: Dict[str, BccConfig] = None

    # the password that was used to encrypt the private key
    private_key_password: Optional[bytes] = None

    @property
    def backends_dict(self) -> Dict[str, BccConfig]:
        """A map of the available BCC instances"""
        if self._backends_dict is None:
            self._backends_dict = {item.name: item for item in self.backends}
        return self._backends_dict

    @model_validator(mode="after")
    def dashboard_url_required_for_email(self) -> "AppConfig":
        """Silently sending mail with dead links is worse than failing at startup"""
        if self.email is not None and not self.notices.dashboard_url:
            raise ValueError(
                "notices.dashboard_url is required when [email] is configured"
            )
        return self

    @classmethod
    def from_json_str(cls, data_str: str) -> "AppConfig":
        """Parses a JSON string into an AppConfig instance

        Args:
            data_str: The JSON string to parse

        Returns:
            the AppConfig instance equivalent to the given JSON string
        """
        conf = json.loads(data_str)
        conf.update(
            conf.pop("general", {}),
        )
        return cls.model_validate(conf)


def get_ip_addr(url: str) -> str:
    """Get the IP address from the url
    Args:
        url: the url to get the IP address from
    Returns:
        the IP address for the given url
    """
    return socket.gethostbyname(url)
