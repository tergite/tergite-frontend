# API design

The rules MSS's REST API follows, so that anyone who knows a resource's name can guess its
endpoints. For contributors adding or changing routes.

## Goals

- A small surface, with as few endpoints as possible.
- One way of doing one thing, unless performance or readability clearly outweighs it.
- Predictable URLs: knowing the resource's name is enough to build any of its endpoints.
- JSON responses only, so client code stays simple.

## Rules

- **URLs** are `/{resource}/({id})`. Every resource has a DTO named after it, e.g. `Job`.
- **Lists** return a paginated object. Build it with `get_paginated_json(data, skip, limit)`,
  and declare `PaginatedListResponse[Item]` as the route's response:

  ```json
  {"skip": 0, "limit": 100, "data": [ ... ]}
  ```

- **Actions** (e.g. cancelling a job) return a `GeneralMessage`:

  ```json
  {"status": "SUCCESS", "message": "..."}
  ```

- **Errors** return a non-2xx status and `{"detail": "..."}`. The central exception handlers
  produce them; routes don't try/except.
- **Filtering** a list uses a Pydantic query model injected with `Depends()` (e.g. `JobQuery`,
  `DeviceQuery`), usually made with `create_partial_model` so every field is optional. `sort`
  is a repeated query parameter, where a leading `-` means descending.
- **A property-only route** (e.g. `GET /jobs/{id}/status`) is allowed only when that property
  is requested far more often than the whole object. It returns `{"{property}": …}`.
- **Every route declares its response**, so the OpenAPI schema describes every body:
  - a route that returns a model gets it as its return annotation;
  - a route that returns a dict it dumped itself, e.g. with `exclude_none=True` (`Job`,
    `Project`, `Device`, the paginated list), declares `responses={200: {"model": …}}`
    instead, as a `response_model` would re-serialise the body and undo that shaping.

  No model overrides `model_dump`; a call site passes the flags it needs.
- **The schema is committed** as `dev/openapi/openapi.json`, written by
  `python -m dev.openapi.export`. `tests/test_openapi.py` fails when it no longer matches the
  app. The dashboard generates its API types from it.

## Endpoint map

| Prefix | Auth | Notes |
| --- | --- | --- |
| `/auth/{provider}/…` | none | `authorize`, `auto-authorize`, `callback`; plus `GET /auth/providers/` and `POST /auth/logout`. There is no password login. |
| `/me` | JWT | the current user: `/me/profile`, `/me/jobs/`, `/me/projects/…`, `/me/tokens/…`, `/me/requests/…`, `/me/notices/…` |
| `/devices` | app token, or none for reads | `GET /`, `GET /{name}`, `WS /ws/{name}` |
| `/calibrations` | none for reads | `GET /`, `GET /{name}` |
| `/jobs` | app token (strict on `POST`) | list, get, `/{id}/status`, create, `/{id}/cancel`, delete. Reads return only the token user's jobs (and jobs with no recorded submitter) unless the user is an admin. |
| `/bookings/{backend}` | JWT | forwarded to the backend: create, cancel, list, `/config` |
| `/counts` | JWT | `/notices`; `/job-submitters` (superusers only) |
| `/admin` | superuser | `/projects/…`, `/users/emails/`, `/notices/…`, and the backend's `/bcc/users/{backend}/…`, `/bcc/recalibration/{backend}/…`, `/bcc/switch/{backend}/on|off` |
| `/health` | none | 200 while MSS runs |

JWT and app tokens are explained in [auth.md](auth.md#how-it-works-in-mss). Interactive docs
are at `/docs` when `general.environment` is `development`.
