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

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    MongoDsn,
    RedisDsn,
    computed_field,
    field_validator,
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
    url: MongoDsn
    redis_url: RedisDsn = "redis://tergite-redis:6379/0"


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

    @computed_field
    @property
    def ip_address(self) -> str:
        """The IP address of the server where the device is"""
        return get_ip_addr(self.url.host)


class PuhuriConfig(BaseModel):
    """Configuration for Puhuri, a resource management platform for HPC systems and Quantum Computers"""

    # turn puhuri synchronization OFF or ON, default=true
    is_enabled: bool = True

    # the URI to the Puhuri WALDUR server instance
    # Please contact the Puhuri team to get this.
    waldur_api_uri: str = ""

    # The access token to be used in the Waldur client [https://docs.waldur.com/user-guide/] to connect to Puhuri
    # Please contact the Puhuri team on how to get this from the UI
    waldur_client_token: str = ""

    # The unique ID for the service provider associated with this app in the Waldur Puhuri server
    # Please contact the Puhuri team on how to get this from the UI
    provider_uuid: str = ""

    # the interval in seconds at which puhuri is polled. default is 900 (15 minutes)
    poll_interval: int = 900


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
    # For Puhuri (openID), register an application at https://webapp.prod.puhuri.eduteams.org/sp_request
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

    # config fields that are not used to create the client
    _non_client_fields = {
        "client_type",
        "redirect_url",
        "email_regex",
        "roles",
        "email_domain",
    }


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

    # configuration for one database; it might become possible to add multiple databases
    database: DatabaseConfig

    # the BCC instances connected to this MSS instance
    backends: List[BccConfig]

    # configuration for authentication
    auth: AuthConfig

    # configration for puhuri
    puhuri: PuhuriConfig

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
