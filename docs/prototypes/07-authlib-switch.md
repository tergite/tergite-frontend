# UAT: step 7, MSS on `authlib`

Step 7 signs users in through `libs/authlib` and keeps them in the `Database` like every
other record, so fastapi-users, Beanie and Motor leave MSS. Items 1 to 3 landed as one change,
as authlib reads users through the `Database`. The API tests seed and read through the
`Database` too, so they run on whichever database `TEST_DATABASE_URL` names. Behaviour is kept
except where the changelog says: emails are unique in any case, and the OpenAPI spec names the
OAuth routes `/auth/{provider}/…`, documents the bearer scheme as `HTTPBearer` and logout's
200. Run each check and tick it. The step is signed off when every
box is ticked, or a failure is written beside its box.

## Start

- In `apps/tergite-mss`, with MongoDB on 27017, Redis on 6379, the PostgreSQL of step 4 on
  5432 and the `.venv` synced with `uv sync --all-extras` (step 7 drops fastapi-users, Beanie
  and Motor, and pins pymongo and PyJWT).

## Checks

- [ ] **7.1–7.4: CI's checks pass.** `.venv/bin/black --check .`, `.venv/bin/isort --check-only .`
      and `.venv/bin/python -m pyflakes api services utils libs migrations settings.py tests dev`
      report nothing, and `.venv/bin/pytest tests` (under a minute) gives 732 passed.
- [ ] **7.1, 7.2: fastapi-users and Beanie are gone.**
      `git grep -nE "fastapi_users|beanie|motor" -- api services utils settings.py pyproject.toml`
      finds nothing, and `ls services/auth/users` lists only `__init__.py` and `dtos.py`.
- [ ] **7.3: users are records.** `services/auth/users/dtos.py` holds `User` and `Role` as
      storage schemas, and `migrations/versions/` holds two revisions, the second adding
      `auth_users`, `auth_roles`, `auth_user_roles` and `auth_user_oauth_accounts`;
      `.venv/bin/pytest tests/test_migrations.py` passes.
- [ ] **7.4: the API runs on the database the environment names.**
      `TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/mss-api.db .venv/bin/pytest tests/api -q`
      passes, as it does with the variable unset (MongoDB).
- [ ] **The step 1.1 contract holds.** `.venv/bin/pytest tests/api/rest/test_auth_contract.py -v`
      passes: the session JWT's claims and audience, the login cookie and redirect, logout,
      the user and project dependencies, and `auth_users`' seven `oauth_accounts` fields.
- [ ] **The OpenAPI spec changes only as foreseen.**
      `git diff 4260c72 -- dev/openapi/openapi.json` shows the OAuth paths becoming
      `/auth/{provider}/…` and `/auth/app/{provider}/…`, `HTTPBearer` beside `APIKeyCookie` on
      every user route, the app-token scheme's `tokenUrl` as `/me/tokens/`, logout's 200 with
      `{"message": "logged out"}`, and `UserRead.id` as a 24-hex string.
- [ ] **The docs say where auth stands.** The changelog has one Changed entry, warning that
      startup fails while two users' emails differ only in case; MSS's `DESIGN.md` §2, §3, §5
      and §7 describe authlib, users as records and the database the API tests run on.
- [ ] **The real stack still works end to end.** With docker running,
      `BACKEND_REPO=<the tergite-backend repository> ./dev/e2e_test.sh` from the repository
      root passes. It prunes unused docker containers, networks and images first.
- [ ] **The baselines still hold.** With docker running and port 8002 free,
      `./dev/perf/record.sh /tmp/perf-07 && python3 dev/perf/compare.py dev/perf/baselines /tmp/perf-07`
      exits 0, or fails only on a p95 within 13 ms of the baseline, or on peak MongoDB
      connections near 27 against 17.
      **2026-10-24: fails only on MongoDB connections, 27 against 17,** with Beanie's client
      gone, so steps 3 to 6 put that excess on the wrong cause. MSS holds one MongoDB client;
      it keeps 22 connections through the load against the baseline's 15. The likely cause is
      the storage layer's native async client, in since step 3, which holds a connection per
      operation in flight, where Motor ran operations on a small thread pool. No request
      failed, and p95 is equal or better: 44 ms aggregate against 48.

## Not covered here

- Moving an existing deployment's data from MongoDB to SQL, which no step of the plan
  includes.
