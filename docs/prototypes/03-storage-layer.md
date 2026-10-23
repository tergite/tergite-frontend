# UAT: step 3, the storage layer, MongoDB first

Step 3 puts every MSS service except the Beanie `User` behind one `Database` in `libs/storage`,
queried in MongoDB's own dialect, and keeps the request log in Redis behind a `Database` of
its own. The API behaves as before, with two visible differences: ids in the OpenAPI
schema carry their 24-hex pattern, and listing jobs fails on a malformed job instead of
silently skipping it. Run each check and tick it. The step is signed off when every box is
ticked, or a failure is written beside its box.

## Start

- In `apps/tergite-mss`, with MongoDB on 27017 and Redis on 6379, and the `.venv` synced
  with `uv sync --all-extras`.

## Checks

- [ ] **3.1–3.7: CI's checks pass.** `.venv/bin/black --check .` and
      `.venv/bin/python -m pyflakes api services utils libs settings.py tests dev` report nothing, and
      `.venv/bin/pytest tests` (about 18 minutes) gives 1013 passed.
- [ ] **3.1: libs depends on nothing above it.**
      `git grep -nE "^(from|import) (api|services|settings)" -- libs` finds nothing, and
      `.venv/bin/pytest tests/libs` passes, including
      `test_derive_id_gives_the_ids_generate_linked_id_did`, which pins the personal project ids.
- [ ] **3.2: one store names each database.** `git grep -lE "pymongo|bson" -- libs` lists
      only `libs/storage/mongo/*` and `libs/storage/base/ids.py`, which borrows bson's
      ObjectId shape to generate ids; `git grep -l "import redis" -- api services utils libs`
      lists only `libs/storage/redis/store.py`.
- [ ] **3.2: the dialect is MongoDB's.**
      `git grep -nE "\b(Eq|Ne|In|NotIn|Range|And|Or|Set|Inc|AddToSet|Pull)\(" -- api services`
      finds nothing, `git grep -nE "def _?build_|\bwhere *=" -- api services libs` finds
      nothing, and `tests/libs/storage/test_database.py` shows unknown operators refused.
- [ ] **3.3: routes get the Database.** `git grep -n "MongoDbDep\|get_default_mongodb" -- .`
      finds nothing, and `api/rest/dependencies.py` defines `DatabaseDep`.
- [ ] **3.4: the request log is in Redis.** `api/rest/database.py` opens it a `Database` on
      `database.redis_url`, `services/request_log/` holds `record_request` and
      `is_request_recorded`, and `tests/api/rest/test_middleware.py` finds each request in the
      `request_logs` hash with an expiry. `tests/libs/storage/redis` is the old
      `tests/test_store.py`, ported.
- [ ] **3.5, 3.7: Beanie keeps only the users.** `utils/mongodb.py` is gone,
      `git grep -n "init_beanie(" -- .` finds one call, in `services/auth/service.py`, with
      `document_models=[User]`, and `git grep -n "(Document)" -- services` lists only `User`.
- [ ] **3.6: ObjectIds stay at the User boundary.**
      `git grep -l PydanticObjectId -- api services utils libs` lists only `api/rest/auth.py`,
      `services/auth/users/dtos.py`, `services/auth/projects/manager.py`,
      `services/auth/projects/routers/__init__.py`, `services/auth/projects/routers/utils.py`,
      `services/external/bcc/service.py` and `services/notices/emails.py`; each use reads or
      builds a Beanie `User` id.
- [ ] **The baselines still hold.** With docker running and port 8002 free,
      `./dev/perf/record.sh /tmp/perf-03 && python3 dev/perf/compare.py dev/perf/baselines /tmp/perf-03`
      exits 0. The run seeds the e2e fixtures with ObjectId ids, as existing data holds them, so
      no route failing is also the check that step 3 still reads old records. Two runs on
      unchanged code have moved per-route p95 by up to 13 ms and peak MongoDB connections by up
      to 3, past the 10 ms and 2-connection noise floors; if this run fails only on such a
      measure, rerun it once before reading it as a regression.
      **2026-10-24, after the request log moved to Redis: fails on two measures.** GET `/jobs/`
      p95 is 69 ms against 56, within the 13 ms noise. Peak MongoDB connections are 26 against
      17, which is not noise: MSS holds two clients until step 7, PyMongo's for the `Database`
      and Motor's for Beanie's users, each with its own pool. Every other route is within
      noise (GET `/me/notices/` 28 ms, GET `/devices/` 26 ms), and no request failed. The first
      run, with the request log in MongoDB, had doubled p95 (GET `/me/notices/` 110 ms) and
      peaked at 32 connections.

## Not covered here

- The SQL backend is step 4; only `mongodb://` and `mongodb+srv://` URLs open a `Database`.
- `dev/e2e_test.sh` needs a clone of tergite-backend; it runs at the end of steps 7 and 9.
