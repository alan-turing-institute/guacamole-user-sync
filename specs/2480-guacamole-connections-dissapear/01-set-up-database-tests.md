# Plan

## Add database unit tests that don't require an external PostgreSQL instance

**Goal:** stand up a minimal, correctly-configured SQLite-backed test fixture that
exercises `guacamole_user_sync/postgresql/postgresql_backend.py` against the real
Guacamole schema, and add just enough of a test to prove the fixture is wired up
correctly. This is scaffolding, not a full database test suite — a follow-up
task can build additional CRUD/update coverage on top of it.

**Approach:** use SQLite as a stand-in database, built from the **actual**
production schema file
`guacamole_user_sync/postgresql/guacamole_schema.1.5.5.sql`, rather than a
hand-maintained subset. No new dependency is needed: `sqlite3` is in the Python
standard library (used via SQLAlchemy's built-in dialect), and `sqlparse` is
already a project dependency, already used to split this exact file in
`guacamole_user_sync/postgresql/sql.py`.

1. **Add the fixture directly to `tests/conftest.py`** (no new test module):
   - Split the file with `sqlparse.split()` (same mechanism as
     `GuacamoleSchema.commands()` in `sql.py`).
   - Skip statements containing `DO $$` — these are the 5 Postgres-only blocks
     that `CREATE TYPE ... AS ENUM (...)` (for
     `guacamole_connection_group_type`, `guacamole_entity_type`,
     `guacamole_object_permission_type`, `guacamole_system_permission_type`,
     `guacamole_proxy_encryption_method`). SQLite has no `CREATE TYPE`/enum
     support and no PL/pgSQL, so these can't run as-is.
   - Execute every remaining statement (all `CREATE TABLE IF NOT EXISTS` and
     `CREATE INDEX IF NOT EXISTS` statements) against an in-memory SQLite
     connection. **Verified with a manual spike:** doing exactly this creates
     all 23 real tables and 61 indexes with **zero errors** — column types like
     `serial`, `bytea`, `timestamptz`, and the enum type names are simply
     unenforced type names to SQLite (it doesn't validate them), so the table
     and index DDL runs unmodified.
   - Wrap a `Session` bound to that engine and inject it into
     `PostgreSQLBackend(connection_details=..., session=session)` — reusing the
     backend's existing `session` constructor argument, so no production code
     changes are required.

2. **Enable `PRAGMA foreign_keys=ON`.** This is mandatory, not optional — it's
   the closest SQLite gets to matching real PostgreSQL's FK-enforcement
   behaviour (Postgres always enforces declared `REFERENCES ... ON DELETE
   CASCADE`/`SET NULL`; SQLite does not, unless told to). Because SQLite only
   honours this pragma on the DBAPI connection it was issued on, register it
   via a SQLAlchemy `event.listens_for(engine, "connect")` hook so it's applied
   to every new connection the engine opens, not just a one-off `execute()`
   call that could be bypassed by pool/connection reuse.

3. **Isolate every test's database — safe for parallel and sequential runs.**
   No test may observe another test's data, in either order:
   - The fixture must be **function-scoped**, creating a brand-new in-memory
     SQLite engine (and running the schema DDL) for every single test that
     requests it. Never share one engine/connection across tests via a
     session- or module-scoped fixture.
   - Because each test gets its own fresh `:memory:` engine with no shared
     state (no shared file path, no shared connection pool, no module-level
     globals), this is safe both for sequential runs and for parallel workers
     (e.g. `pytest-xdist`), which each run in separate processes anyway.
   - Do not use a filesystem-backed SQLite file for this fixture (which would
     require careful unique-per-test naming/cleanup to avoid collisions); the
     in-memory engine per test sidesteps that entirely.

4. **Keep the test count to a minimum.** Add a single smoke test that performs
   a write-then-read through `PostgreSQLBackend` against the real schema
   (insert a `GuacamoleEntity` via `add_all`, then `query` it back and check the
   persisted values) — proving the ORM models in `orm.py`, the real schema, and
   the backend session wiring are all compatible end to end. Do **not** add a
   separate test asserting the schema/tables were created — that's implicitly
   covered by the smoke test succeeding at all (if the schema failed to build,
   the insert/query would error). Also explicitly **not** in scope for this
   task: a full suite covering every `PostgreSQLBackend`/`PostgreSQLClient`
   method, update/delete branches, `assign_users_to_groups`, etc. — that's
   deferred to a follow-up once this scaffolding is confirmed to work.

5. **Accepted limitation:** with the enum-creation blocks skipped, enum-typed
   columns (e.g. `guacamole_entity.type`) are unconstrained in SQLite — invalid
   enum values wouldn't be rejected the way real Postgres would reject them.
   This is a property of the SQLite stand-in, not something these tests need to
   verify; schema/DDL correctness against real Postgres syntax continues to be
   covered by the existing `test_ensure_schema` test (mocked backend + capsys).

6. **No dependency or config changes needed.** No changes to `pyproject.toml`,
   CI, or `tool.hatch.envs.test` are required.

7. **Verify locally** with `hatch run test:all` (`coverage run -m pytest tests` +
   `coverage report`) and the lint/type-check envs
   (`hatch run lint:style`, `hatch run lint:typing`) before opening the PR.
