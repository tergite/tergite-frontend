# Backends

How MSS connects to the quantum backends ([tergite-backend](https://github.com/tergite/tergite-backend),
also called BCC), and how they talk to each other.

## Adding a backend

1. Start the [tergite-backend](https://github.com/tergite/tergite-backend) instance.
2. Exchange public keys. MSS and the backend sign what they send each other and check it
   against the other's public key:
   - copy MSS's `public-mss-key.pem` to the backend, which reads it from
     `BCC_MSS_PUBLIC_KEY_PATH`;
   - copy the backend's public key next to MSS, as `public-backend-key.pem` or the path you
     give below.

   To make MSS's public key from its private one:

   ```shell
   openssl rsa -pubout -in private-mss-key.pem -out public-mss-key.pem
   ```

3. Add a `[[backends]]` entry to `mss-config.toml`:

   ```toml
   [[backends]]
   # the backend's BCC_DEFAULT_PREFIX; the name users pick it by in the SDK and dashboard
   name = "simulator"
   # where the backend is running
   url = "http://127.0.0.1:8000"
   # its public key; a relative path is in the folder MSS starts in
   public_key_path = "public-backend-key.pem"
   # whether to check that its websocket comes from the host of `url`; default true
   is_strict_ip = false
   # optional: the URL clients upload jobs to, e.g. through a reverse proxy; default `url`
   # public_url = "http://proxy.example.com/simulator"
   ```

4. Restart MSS. The backend shows as online once it connects its websocket.

## MSS → backend: signed HTTP

MSS holds one `BccClient` per `[[backends]]` entry (`services/external/bcc/service.py`),
created at startup. `bcc.get_client(name)` looks one up and raises `UnknownBccError` for an
unknown name.

Every call goes through `BccClient._request`, which:

- signs the call with MSS's private key (`PRIVATE_KEY_FILE`) in `x-mss-*` headers: the user,
  a fresh nonce, a timestamp, whether the user is an admin, the method and the path. The
  backend refuses a nonce it has seen (its `mss_nonce` table);
- raises `BccHttpError` with the backend's status on an error answer;
- turns a connection error or timeout into `ServiceUnavailableError` (503).

**MSS stores no bookings and no backend users.** `/bookings` and `/admin/bcc/users` forward
to the backend on the user's behalf.

## Backend → MSS: the device websocket

A backend pushes its state over `WS /devices/ws/{name}`.

**The handshake** carries `x-id`, `x-request-id`, `x-timestamp` and `x-signature`.
`get_verified_device_name` (`api/utils.py`) checks the signature against that backend's
`public_key_path`, the source IP (unless `is_strict_ip = false`), the timestamp's age
(`bcc_nonce_ttl`) and that the nonce is new (`bcc_nonces`).

**Online or offline.** A backend opens a socket per process, and each may reach a different
MSS process, so liveness is kept in the database:

- Each socket is a `device_connections` record while it is open. The MSS process holding it
  renews it every 30 s (`CONNECTION_REFRESH_SECONDS`) to expire 90 s ahead
  (`CONNECTION_TTL_SECONDS`), so a dead process's records lapse.
- A device is online while it has a live connection and is not switched off
  (`switched_off_devices`). Its stored `is_online` and `last_online` are updated on each
  change, and for every device on each refresh.

**The events.** Each frame is a `DeviceEvent`, dispatched through `EVENT_HANDLERS` in
`services/devices/events.py`:

| Event | Effect |
| --- | --- |
| `initialized` | upsert the device |
| `recalibrated` | insert the calibration into `calibrations`, and append it to `calibrations_logs` |
| `job_updated` | update the job; on its first resource-usage report, take its QPU seconds from the project |
| `switched_off` | mark the device switched off |
| `switched_on` | mark the device switched on |

MSS replies to each frame with an `EventResponse` and never closes the socket over a bad one:
a validation error is `{"status": "error", "detail": …}`, and a device editing another
device's record gets `forbidden`.

### Adding or changing an event

tergite-backend's OpenAPI spec is the source of what events carry. `dev/openapi/sync.sh`
copies it into `dev/openapi/bcc.json` and generates `services/external/bcc/events.py`;
`tests/test_openapi.py` fails when that is stale.

- **Nothing undeclared passes.** MSS reads each event with the generated model and keeps only
  the fields its own schemas declare. A test fails on a field the spec declares that MSS
  neither keeps nor lists in `_NOT_KEPT` with a reason.
- **Changes are additive.** A new field is optional with a default. A field is never renamed,
  retyped or removed in one release: it is deprecated for one release first.
- **In order:** the backend's spec first; then MSS syncs it and declares where it keeps the
  field; then the SDK regenerates its models.

A new event also needs an enum member and its entry in `_EVENT_DATA_CLASSES`
(`services/devices/dtos.py`), and a handler in `EVENT_HANDLERS`.
