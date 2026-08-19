# Tech Stack

## Overview

`guacamole-user-sync` is a small, long-running Python daemon that keeps a
[Apache Guacamole](https://guacamole.apache.org/) PostgreSQL database in sync
with the users and groups defined in an LDAP directory (e.g. Microsoft
Active Directory). It reads users/groups from LDAP on a fixed interval and
reconciles them against Guacamole's `guacamole_entity`, `guacamole_user`,
`guacamole_user_group`, and `guacamole_user_group_member` tables.

The project is intentionally small and dependency-light: it is packaged as a
single Docker image intended to run as a sidecar/init-style container next to
a Guacamole deployment, not as a library or service with an API.

## Language & runtime

- **Python 3.11** (`requires-python = "==3.11.*"`), pinned exactly rather than
  a range — the project targets a single supported runtime.
- No async runtime — the app is a single-threaded, blocking, `while True` +
  `time.sleep()` loop (`synchronise.py`). Chosen for simplicity: sync runs are
  short and infrequent (default `REPEAT_INTERVAL=300s`), so there is no need
  for concurrency, scheduling libraries, or async I/O.

## Core dependencies

| Library | Version | Purpose |
|---|---|---|
| [`ldap3`](https://ldap3.readthedocs.io/) | 2.9.1 | Pure-Python LDAP client used to bind to and query the directory server for users/groups. |
| [`psycopg`](https://www.psycopg.org/psycopg3/) (v3, with the `[c]` C extension in the built image) | 3.2.3 | PostgreSQL DB-API driver, used as the SQLAlchemy backend. |
| [`SQLAlchemy`](https://www.sqlalchemy.org/) | 2.0.36 | ORM/Core layer over PostgreSQL — declarative models for Guacamole's schema plus a thin query/session wrapper. |
| [`sqlparse`](https://sqlparse.readthedocs.io/) | 0.5.3 | Splits/parses the raw Guacamole schema `.sql` file into individual statements (and pulls out comments for logging) before executing them via SQLAlchemy. |

All dependency versions are pinned exactly (`==`) rather than range-constrained,
consistent with an application (not a library) that ships as a container image.

## Project layout

```
guacamole_user_sync/
  ldap/            LDAPClient — connects to and queries the LDAP server
  models/          Plain dataclasses (LDAPUser, LDAPGroup, LDAPQuery,
                   GuacamoleUserDetails) and custom exceptions (LDAPError,
                   PostgreSQLError)
  postgresql/
    postgresql_backend.py   Thin session/engine wrapper around SQLAlchemy
                             (add_all/delete/query/execute_commands)
    postgresql_client.py    Sync/reconciliation logic (diff LDAP vs DB state)
    orm.py                  SQLAlchemy declarative models mapping Guacamole's
                             own tables (entity, user, user_group, member)
    sql.py                  Loads/parses versioned Guacamole schema SQL files
    guacamole_schema.*.sql  Vendored copy of Guacamole's official schema DDL
synchronise.py     Entry point: reads env vars, builds clients, runs the loop
tests/              pytest suite with mocked LDAP/PostgreSQL fixtures
```

## Key design decisions

- **Idempotent, declarative sync, not incremental diffing against history.**
  Each cycle re-reads the full desired state from LDAP and reconciles it
  against the full current state in PostgreSQL (add what's missing, remove
  what's no longer present) rather than tracking deltas. This keeps the
  daemon stateless between runs and self-healing after any missed cycle,
  DB restart, or manual DB edit.

- **Guacamole's schema is vendored and applied at startup, not assumed to
  pre-exist.** `postgresql/guacamole_schema.<version>.sql` is a copy of
  Guacamole's own official JDBC-auth schema DDL, executed idempotently via
  `ensure_schema()` before every sync. `SchemaVersion` is an explicit enum
  (currently only `v1_5_5`) so schema compatibility is a first-class,
  versioned concept rather than implicit.

- **ORM models mirror Guacamole's tables exactly; the app owns no schema of
  its own.** `orm.py`'s `GuacamoleEntity`/`GuacamoleUser`/`GuacamoleUserGroup`/
  `GuacamoleUserGroupMember` map 1:1 onto Guacamole's existing tables. This
  tool is a client of Guacamole's data model, not the owner of it — it must
  track Guacamole's schema, not the other way around.

- **Fail-soft per subsystem.** LDAP query failures and PostgreSQL update
  failures are caught independently (`LDAPError`, `PostgreSQLError`) and only
  logged as warnings; the process keeps running and retries on the next
  interval rather than crashing. This favours availability of the sync loop
  over surfacing every transient directory/DB blip.

- **Passwords are never synced — Guacamole users are set up for
  externally-verified auth.** New `guacamole_user` rows get a random
  32-byte `password_hash`/`password_salt` (`secrets.token_bytes`) that can
  never be used to log in directly. Authentication is expected to happen via
  Guacamole's LDAP/SSO auth extension in front of this JDBC-backed user
  store; this tool only manages entity/group membership, not credentials.

- **Plain dataclasses instead of Pydantic/attrs for LDAP-facing models.**
  `LDAPUser`, `LDAPGroup`, `LDAPQuery`, `GuacamoleUserDetails` are stdlib
  `@dataclass`es — the shapes are internal and small enough that a
  validation framework would add a dependency without adding value.

- **Thin, hand-rolled PostgreSQL backend instead of the SQLAlchemy ORM's
  full unit-of-work/relationship features.** `PostgreSQLBackend` exposes only
  `query`/`add_all`/`delete`/`execute_commands`, each opening its own short
  session/transaction. There are no relationships or cascades between the
  ORM models — associations (e.g. group membership) are resolved manually in
  `PostgreSQLClient`, keeping the sync logic explicit and easy to trace.

- **Configuration entirely via environment variables, validated at startup.**
  `synchronise.py` reads all config from env vars and raises immediately on
  missing required ones (`LDAP_HOST`, `LDAP_GROUP_BASE_DN`, etc.) before
  entering the loop — a fail-fast startup rather than deferring errors into
  the sync cycle. This suits a container-first deployment model with no
  config file.

## Build & distribution

- **Packaging**: [Hatch](https://hatch.pypa.io/) / `hatchling` build backend;
  version is derived from `guacamole_user_sync/__about__.py`
  (`tool.hatch.version`).
- **Docker**: multi-stage build (`Dockerfile`).
  - Builder stage (`python:3.11.9-slim`) uses `hatch` to freeze dependencies,
    then builds and repairs (`auditwheel`) manylinux wheels for everything,
    including compiling `psycopg[c]` from source for a self-contained wheel.
  - Final stage runs on `gcr.io/distroless/python3-debian12:debug` — a
    minimal, non-shell-by-default base image chosen to minimize attack
    surface for a service that holds directory-bind and DB credentials.
    Wheels are installed with `--no-index` from the local wheelhouse only
    (no PyPI access needed at runtime), and the app runs under
    `dumb-init` as PID 1 for correct signal handling in the sync loop.
  - Images are published to `ghcr.io/alan-turing-institute/guacamole-user-sync`
    on pushes to `main` and on version tags.

## Tooling

- **Environment/task runner**: [Hatch](https://hatch.pypa.io/) environments
  (`test`, `lint`) drive both local dev and CI — `hatch run test:all`,
  `hatch run lint:all`.
- **Linting/formatting**: `black` (formatting) + `ruff` with `select = ["ALL"]`
  (broad rule set, with a small, explicit ignore list for docstring/assert
  rules that conflict with the project's style or pytest).
- **Type checking**: `mypy --strict`, with `ignore_missing_imports` overrides
  for untyped third-party packages (`ldap3`, `sqlalchemy`, `sqlparse`,
  `pytest`). Strict mode reflects that this is a small codebase where full
  type coverage is cheap to maintain and catches integration mistakes
  between the LDAP and PostgreSQL layers.
- **Testing**: `pytest` + `coverage[toml]`, with hand-rolled LDAP/PostgreSQL
  mocks in `tests/mocks.py` and shared fixtures in `tests/conftest.py` rather
  than a real LDAP/PostgreSQL test double stack — keeps the test suite fast
  and dependency-free.
- **CI**: GitHub Actions — separate workflows for tests
  (`test_code.yaml`, with PR coverage comments via
  `python-coverage-comment-action`), linting (`lint_code.yaml`), coverage
  publishing (`test_coverage.yaml`), and Docker image publishing
  (`publish_docker.yaml`) to GHCR.

## Deployment model

Single container, configured entirely through environment variables (see
`README.md`), designed to run continuously alongside a Guacamole + PostgreSQL
deployment (e.g. as an extra service in the same Docker Compose/Kubernetes
stack) and periodically reconcile Guacamole's user/group tables with the
LDAP directory that is the actual source of truth for identity.
