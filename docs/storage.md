# Storage

How MSS keeps its data, for contributors who add or change a schema. The code is in
`libs/storage/`, which imports no app code.

## One `Database`, three kinds of store

MSS has one `Database`, opened at startup with every service's schemas (gathered in
`services/schemas.py`) and given to routes as `DatabaseDep`. It picks its store from the
URL's scheme in `[database]`:

| URL | Store |
| --- | --- |
| `mongodb://` | `MongoStore` |
| `postgresql+asyncpg://` | `SqlStore` |
| `sqlite+aiosqlite://` | `SqlStore` |

Nothing outside `libs/storage/<store>` names a database technology.

## Schemas

A schema is a Pydantic `Schema` whose `__storage__` names its table, key, unique fields,
indexes, expiring field, references and `indexed_lists`.

- **Ids** are `Id` strings; MongoDB keeps them as ObjectIds.
- **Expiry.** No store returns a record past its expiring field.
- **`should_skip_invalid`.** `get` and `find` leave out stored records that fail validation,
  with a warning; other reads raise, and writes always raise. Jobs and notices set it, as
  MongoDB holds older shapes of both.

## Queries

Services query in MongoDB's own dialect, limited to what every store can translate:

```python
filter={"user_id": {"$in": [user_id, None]}}
update={"$set": {...}, "$inc": {...}}
sort=["-created_at"]
skip=0, limit=100
```

`Database` refuses an unknown operator or field, and an update that changes a key, before a
store sees it. A service builds its filters privately from its arguments; routes never build
one.

## MongoDB

- A collection per schema, with a `$jsonSchema` validator and the indexes `__storage__` asks
  for. A TTL index deletes expired records.
- **Migrations.** A revision that changes stored values has a JSON of updates, both ways, in
  `migrations/mongodb/`, named after the revision. `mss migrate` applies the pending ones in
  Alembic's order (`python -m migrations.mongodb upgrade`). Each also has `.upgrade.js` and
  `.rollback.js` for mongosh. Both record what ran in `mongodb_migrations`.

## SQL

`libs/storage/sql/tables.py` makes a table per schema:

- a column per scalar field;
- a `JSON` column per nested field, read and written whole, never queried;
- a `row_id` that keeps insertion order;
- a child table, one row per element, for each list in `indexed_lists` or `references`
  (`auth_project_user_ids`, `notice_dismissed_by`, `request_target_user_ids`);
- for a list of models, a column per element field, set whole and matched with `$elemMatch`,
  as a user's OAuth accounts are.

A query on a JSON field, or a write to part of one, is refused: that is the signal to give it
a table of its own. Alembic migrates the tables (`migrations/`), and `tests/test_migrations.py`
fails when a schema changed without a revision. As SQL has no TTL index, a task deletes
expired rows hourly.

## The tables

| Table | Holds |
| --- | --- |
| `auth_users`, `auth_roles` | users, as fastapi-users wrote them, and their roles |
| `jobs` | jobs |
| `devices` | devices, as their backends last reported them |
| `calibrations`, `calibrations_logs` | the latest calibration per device, and their history, indexed on `(name, last_calibrated desc)` |
| `notices` | notices, expiring at `expires_at` |
| `device_connections` | the backends' open websockets, expiring at `expires_at`; see [backends.md](backends.md) |
| `switched_off_devices` | devices switched off |
| `deleted_auth_projects` | deleted projects, kept rather than dropped |
| `bcc_nonces` | the backends' websocket nonces |

**Nonces.** Each backend websocket handshake's nonce is kept in `bcc_nonces` (unique on
`nonce`) for `bcc_nonce_ttl` seconds; past that, the handshake's timestamp is refused as too
old anyway. One is written per connection, never per message or request. `claim_bcc_nonce`
returns False for a nonce already claimed, which refuses a replay in one write, across every
MSS process sharing the database.

## Testing

`tests/libs/storage/test_conformance.py` runs every `Database` method on MongoDB, PostgreSQL
and SQLite, and each service's storage test (`tests/services/*/test_*_storage.py`) runs on all
three too.
