# UAT: step 3, the storage layer, MongoDB first

Step 3 puts every MSS service except the Beanie `User` behind one `Database` in `libs/storage`,
and drops Redis. The API behaves as before, with two visible differences: ids in the OpenAPI
schema carry their 24-hex pattern, and listing jobs fails on a malformed job instead of
silently skipping it. Run each check and tick it. The step is signed off when every box is
ticked, or a failure is written beside its box.

## Start

- In `apps/tergite-mss`, with MongoDB on 27017 (Redis is no longer needed), and the `.venv`
  synced with `uv sync --all-extras` (step 3 drops redis and hiredis).

## Checks

- [ ] **3.1–3.7: CI's checks pass.** `.venv/bin/black --check .` and
      `.venv/bin/python -m pyflakes api services utils libs settings.py tests dev` report nothing, and
      `.venv/bin/pytest tests` (about 18 minutes) gives 931 passed.
- [ ] **3.1: libs depends on nothing above it.**
      `git grep -nE "^(from|import) (api|services|settings)" -- libs` finds nothing, and
      `.venv/bin/pytest tests/libs` passes, including
      `test_derive_id_gives_the_ids_generate_linked_id_did`, which pins the personal project ids.
- [ ] **3.2: one store names MongoDB.** `git grep -lE "pymongo|bson" -- libs` lists only
      `libs/storage/mongo/*` and `libs/storage/base/ids.py`, which borrows bson's ObjectId
      shape to generate ids.
- [ ] **3.3: routes get the Database.** `git grep -n "MongoDbDep\|get_default_mongodb" -- .`
      finds nothing, and `api/rest/dependencies.py` defines `DatabaseDep`.
- [ ] **3.4: Redis is gone.**
      `git grep -il redis -- api services utils libs settings.py pyproject.toml` finds nothing,
      and `services/request_log/` holds `record_request` and `is_request_recorded`.
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
      **Failed on 2026-10-23:** per-route p95 rose to about twice the baselines (GET
      `/me/notices/` 110 ms against 22, GET `/devices/` 74 against 25, GET `/jobs/` 110 against
      56) and peak MongoDB connections to 32 against 17, with no failed requests. Step 2's
      commit, recorded the same day, stayed within noise, so the cost is step 3's. The storage
      layer's own calls take under 1 ms on these lists; the suspects are the request-log insert
      every request now awaits (3.4) and the second client Beanie's users keep (3.7).

## Not covered here

- The SQL backend is step 4; only `mongodb://` and `mongodb+srv://` URLs open a `Database`.
- `dev/e2e_test.sh` needs a clone of tergite-backend; it runs at the end of steps 7 and 9.
