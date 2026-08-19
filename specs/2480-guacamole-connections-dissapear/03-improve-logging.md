# Plan

## Error handling should log at ERROR with the full traceback

Split out from
`specs/2480-guacamole-connections-dissapear/02-test-recovery.md` (formerly
§5, a side quest identified while planning the LDAP-blip recovery test).
Implementation must follow `specs/coding-guidelines.md` (precise types,
brief docstrings/comments, verify with `hatch run test:all` / `hatch run
lint:all`) and the conventions in `specs/tech_stack.md`.

## 1. Audit of existing error handling

Audited every `try`/`except` block in `guacamole_user_sync/`:

| Location | Log call | Includes traceback? |
|---|---|---|
| `ldap/ldap_client.py:59-62` (`connect`, `LDAPSocketOpenError`) | `logger.error(msg)` with `# noqa: TRY400` | **No** |
| `ldap/ldap_client.py:63-66` (`connect`, `LDAPBindError`) | `logger.error(msg)` with `# noqa: TRY400` | **No** |
| `ldap/ldap_client.py:67-70` (`connect`, `LDAPException`) | `logger.error(msg)` with `# noqa: TRY400` | **No** |
| `ldap/ldap_client.py:108-111` (`search`, `LDAPSessionTerminatedByServerError`) | `logger.error(msg)` with `# noqa: TRY400` | **No** |
| `ldap/ldap_client.py:112-115` (`search`, `LDAPException`) | `logger.error(msg)` with `# noqa: TRY400` | **No** |
| `postgresql/postgresql_backend.py:73-80` (`execute_commands`, `SQLAlchemyError`) | `logger.warning(...)` | **No** (also wrong level — see below) |
| `postgresql/postgresql_client.py:142-147` (`ensure_schema`, `SQLAlchemyError`) | *(no log call at all — re-raised as `PostgreSQLError` with no logging)* | **No** |
| `postgresql/postgresql_client.py:63-90`, `98-101`, `103-122` (`assign_users_to_groups`, `StopIteration`) | `logger.debug(...)` | N/A — expected control flow, not an error; debug level is appropriate here and out of scope |
| `synchronise.py:76-81` (`synchronise`, `LDAPError`) | `logger.warning(...)` | **No** |
| `synchronise.py:83-88` (`synchronise`, `PostgreSQLError`) | `logger.warning(...)` | **No** |

**Finding:** every genuine error path in `ldap_client.py` calls
`logger.error(msg)` and explicitly suppresses ruff's `TRY400` rule (which
exists precisely to catch this: it recommends `logger.exception(...)` inside
an `except` block so the stack trace is captured). As written, the log
records the friendly message but **not** the original exception or its
traceback — the `# noqa: TRY400` comments mark this as a deliberate choice,
but it's the opposite of what's asked for here (error level *and* full
stack trace). The two `synchronise.py`/`postgresql_backend.py` call sites use
`logger.warning`, one level below what's asked for, and also drop the
traceback. `postgresql_client.ensure_schema` doesn't log at all before
re-raising, relying entirely on the caller.

## 2. Proposed verification tests

Add alongside the existing `caplog`-based tests in `tests/test_ldap.py`/
`tests/test_postgresql.py`, no new infrastructure needed: for each `except`
branch above that is meant to represent a genuine failure, assert on the
captured `logging.LogRecord` rather than just `caplog.text`, since only the
record exposes traceback presence:

```python
records = [r for r in caplog.records if r.name == "guacamole_user_sync"]
error_records = [r for r in records if r.levelno == logging.ERROR]
assert error_records, "expected an ERROR-level log record"
assert error_records[0].exc_info is not None
assert error_records[0].exc_text or "Traceback" in caplog.text
```

## 3. Implementation

Fix the finding itself:

- Switch the five `ldap_client.py` sites from `logger.error(msg)  #
  noqa: TRY400` to `logger.exception(msg)` and drop the now-unneeded `noqa`.
- Review whether the two `synchronise.py`/`postgresql_backend.py` warnings
  and the silent `ensure_schema` path should become `logger.exception` at
  `ERROR` level too.

Call this out explicitly in the PR description so it isn't mistaken for
something the test-recovery plan (`02-test-recovery.md`) already does.

## 4. Verification

Once implemented, run `hatch run test:all` and `hatch run lint:all` before
opening the PR, per `specs/coding-guidelines.md`.
