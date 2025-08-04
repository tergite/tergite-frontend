# Authentication and Authorization

This is how MSS authenticates its users and controls their access to the quantum computer resource.

## Authentication

- It uses [Oauth2](https://oauth.net/2/), a standard similar to HTTP in the sense that for any system,
  also called an **Oauth2 client**, to allow its users to authenticate with another system,
  called an **Oauth2 provider**, all that is needed are two strings:
  - `CLIENT_ID`
  - `CLIENT_SECRET`
- The two strings are unique to this system, but are given by the Oauth2 provider
- Common Oauth2 providers include Google, Github, Microsoft, Chalmers (which uses Microsoft)
- Organizations which have a sort of ActiveDirectory can automatically be Oauth2 providers.
- We also use [OpenID Connect](https://openid.net/developers/how-connect-works/) which is a flavour of Oauth2 that requires a third string, a  
  `OPENID_CONFIGURATION_ENDPOINT`, from where to get the configuration of the openID provider.

### How to Set Up a New Oauth2 Provider

- Let's say we want some 'Company B' users to have access to MSS.
- Copy the `mss-config.example.toml` to `mss-config.toml`, and update the configs therein.  
  Note: You could also create a new toml file based on `mss-config.example.toml`  
  and set the `MSS_CONFIG_FILE` environment variable to point to that file.
- Add the new client:

```toml
[[auth.clients]]
# this name will appear in the URLs e.g. http://127.0.0.1:8002/auth/company-b/...
name = "company-b"
client_id = "some-openid-client-id"
client_secret = "some-openid-client-secret"
# the URL to redirect to after user authenticates with the system.
# It is of the format {MSS_BASE_URL}/auth/{provider_name}/callback
redirect_url = "http://127.0.0.1:8002/auth/company-b/callback"
client_type = "openid"
email_regex = ".*"
# Roles that are automatically given to users who authenticate through Company B
# roles can be: "admin", "user", "researcher", "partner". Default is "user".
roles = ["partner", "user"]
# openid_configuration_endpoint is necessary if Company B uses OpenID Connect, otherwise ignore.
openid_configuration_endpoint = "https://proxy.acc.puhuri.eduteams.org/.well-known/openid-configuration"
```

- Start the frontend.
  Instructions are on the [tergite-frontend/README.md](../../../README.md)

## Authorization

- We control access to MSS, and its BCCs using two ways
  - `roles` control basic access to auth-related endpoints e.g. project creation, token management etc.
  - `projects` control access to all other endpoints. To create a job, or get its results etc,
    one must be attached to a project that has more than zero QPU seconds.
- QPU seconds are the number of seconds a project's experiments are allocated on the quantum computer.
- QPU seconds can be increased, decreased etc., but no job can be created without positive QPU seconds.
- A job could run for longer than the allocated project QPU seconds but
  it may fail to update MSS of its results. A user must thus make sure their project has enough QPU seconds.

### How Authorization Works

Here is an interaction diagram of QAL9000 auth showcasing authentication via [MyAccessID](https://ds.myaccessid.org/).

![Interaction diagram of QAL9000 auth showcasing MyAccessID](./assets/qal9000-auth.png)

**The raw editable drawio diagram can be found [in the assets folder](./assets/qal9000-auth.drawio)**

### FAQs

#### - How do we bypass authentication in development?

We use feature flag `auth.is_enabled` property in the `mss-config.toml` file, setting it to `false`

```toml
is_enabled = false
```

**Note: Most endpoints will still require authentication because they depend on the current user**

#### - How do we ensure that in production, authentication is always turned on?

On startup, we raise a ValueError when `auth.is_enabled = false` in the `mss-config.toml` file yet  
config variable `environment = production` and log it.

#### - How do we allow other Tergite components (e.g. tergite backend) to access MSS, without user intervention?

Use app tokens created by any user who had the 'system' role. These app (API) token are created in the tergite dashboard.
Any such token is saved in the `MSS_TOKEN` environment variable in the backend's `.env` file.
The advantage of using app tokens is that they are more secure because they can easily be revoked and scoped.
Since they won't be used to run jobs, their project QPU seconds are expected not to run out.

If you are in development mode, you can just switch off authentication altogether.

**Note: One must set the `MSS_TOKEN` environment variable in Tergite backend or else it will not be able to communicate with the Tergite frontend**

#### - What happens when the `MSS_TOKEN` in Tergite backend or the project it belongs to expires or is deleted.

Unfortunately, currently, the backend will fail with 'Unauthorized' errors in its logs when it attempts to send results to MSS.
The admin must therefore find a way of keeping the `MSS_TOKEN` active.

#### - How do I log in?

- You need to run both [MSS](../) and the [dashboard](../../tergite-dashboard/).
- **Make sure that your `mss-config.toml` files have all variables filled appropriately** for example, both applications should have the same `jwt_secret`.
- The dashboard, when running will redirect you to the login page if you are not already logged in.
- However, you can also log in without running the dashboard first. See the next FAQ.

#### - How do I log in without having to run the dashboard?

- **Make sure that your `mss-config.toml` file has all variables filled appropriately**.
  The `mss-config.example.toml` is a good template to copy from, but it must all placeholder (`<some-stuff>`) must be replaced in the actual `mss-config.toml` file.
- Run the application

```shell
./start_mss.sh
```

- Visit the http://localhost:8002/auth/github/authorize endpoint in your browser if you are running on local host.
- Copy the “authorization_url” from the response and paste it in another tab in your browser. Follow any prompts the browser gives you.
- After you are redirected back to http://localhost:8002/auth/github/callback, you should see an “access_token”. Copy it to your clipboard.  
  If you run into any errors, ensure that the `client_id` and `client_secret` for the `client` table with `name = tergite` in your `mss-config.toml` file are appropriately set.
- You can then try to create an app token or anything auth related using `curl` or [postman](https://www.postman.com/).  
  To authenticate those requests, you must always pass an "Authorization" header of format `Bearer <access_token>`.  
  **Do note that this auth token can only be used on `/auth...` endpoints. It will return 401/403 errors on all other endpoints**.
- Do note also that some endpoints are only accessible to users that have a given role e.g. 'admin' or 'system' etc.

#### - Why do I keep being redirected back to the login page even after successful login?

The likely cause is the `cookie_domain` variable in the `mss_config.toml`. It needs to be the same as the domain you visit the dashboard on in the web browser.  
It also needs to be the same domain that your `MSS_URL` environment variable is in the `.env` file.

**A big culprit is the localhost vs 127.0.0.1. Make sure you use 127.0.0.1 in all both your `.env` and `mss_config.toml`. Visit the browser also at 127.0.0.1:3000**

#### - How does BCC (backend) get authenticated?

- A client (say [tergite](https://github.com/tergite/tergite)) sends a `POST`
  request is sent to `/jobs` on MSS (this app) with an `app_token` in its `Authorization` header
- A new job entry is created in the database, together with a new unique `job_id`.
- MSS then requests BCC for a user token via a POST to `/token`, passing it the `user_id` and the `job_id`, plus some headers signed by MSS's private key
- BCC verifies that the headers are indeed signed by MSS's private key since BCC has a copy of MSS's public RSA key.
- BCC creates a token for the user and if the user does not exist yet, a new one with a random password and email is created
- BCC encrypts that token with MSS's public key so that only MSS can read it, and then sends it back to the requester.
- MSS decrypts the token, and alongside the `upload_url` (which is the `/jobs` url for the given BCC backend), sends it to the client application.
- The client application then posts the job for the given job_id to the backend with the given token in the `Authorization` header.
- Currently, we have not limited this token to be used only once so technically a user could send different experiments
  but with the same job_id. However, the token itself has a short time span to reduce the extent of this.
  In future, we might limit each token to only one request.
- A similar flow is used to download raw logfiles from BCC at `/logfiles/{job_id}` endpoint.
- For all other BCC endpoints, they must be accessed via MSS on behalf of the user.

## Puhuri

[Puhuri](https://puhuri.neic.no/) is an HPC resource management platform that could also be used to manage Quantumm Computer systems.

We need to synchronize MSS's resource management with that in Puhuri

The Puhuri Entity Layout
![Puhuri Layout](./assets/puhuri-entity-layout.png)

### Flows

More information about flows can be found in the [puhuri docs folder](puhuri)

![Selecting resource to report on](./assets/puhuri-resource-usage-reporting-flow.png)

### Assumptions

- When creating components in the puhuri UI, the 'measurement unit's
  set on the component are of the following possible values:
  'second', 'hour', 'minute', 'day', 'week', 'half_month', and 'month'.

### How to Start the Puhuri Sync

- Ensure that the `is_enabled = true` in the `[puhuri]` table in your `mss-config.toml` file
- Ensure all other variables in the `[puhuri]` table in your `mss-config.toml` file are appropriately set e.g.

```toml
[puhuri]
# the URI to the Puhuri WALDUR server instance
# Please contact the Puhuri team to get this.
waldur_api_uri = "<the URI to the Puhuri Waldur server>"
# The access token to be used in the Waldur client [https://docs.waldur.com/user-guide/] to connect to Puhuri
# Please contact the Puhuri team on how to get this from the UI
waldur_client_token = "<API token for a puhuri user who has 'service provider manager' role for our offering on puhuri>"
# The unique ID for the service provider associated with this app in the Waldur Puhuri server
# Please contact the Puhuri team on how to get this from the UI
provider_uuid = "<the unique ID for the service provider associated with this app in Puhuri>"
# the interval in seconds at which puhuri is polled. default is 900 (15 minutes)
poll_interval = "<some value>"
```

- If you wish to start only the puhuri synchronization script without the REST API, run in your virtual environment:

```shell
python -m api.scripts.puhuri_sync --ignore-if-disabled
```

- In order to run both the REST API and this puhuri synchronization script, run in your virtual environment:

```shell
python -m api.scripts.puhuri_sync --ignore-if-disabled & \
  uvicorn --host 0.0.0.0 --port 8000 api.rest:app  --proxy-headers
```
