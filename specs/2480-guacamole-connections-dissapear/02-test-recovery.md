# Plan

## Test that the application recovers after a bad LDAP response

**Goal:** add a regression test that drives `synchronise()`
(`synchronise.py`) end-to-end against the real Guacamole schema, proving (or
disproving) that a transient LDAP blip — a query that momentarily returns 0
groups and 0 users — does not permanently destroy connection access once LDAP
recovers. Follows on from
`specs/2480-guacamole-connections-dissapear/01-set-up-database-tests.md`,
which added the `postgresql_sqlite_backend_fixture` in-memory SQLite fixture;
this plan reuses it rather than mocking `PostgreSQLBackend`. Implementation
must follow `specs/coding-guidelines.md` (precise types, brief docstrings/
comments, verify with `hatch run test:all` / `hatch run lint:all`) and the
conventions in `specs/tech_stack.md`.

## 1. Background: why "connections disappear"

`PostgreSQLClient.update()` (`guacamole_user_sync/postgresql/
postgresql_client.py`) reconciles `guacamole_entity` against the full set of
groups/users LDAP just returned: anything registered in the database but not
present in LDAP's response is deleted (`update_groups`, `update_users`). This
is correct for a real, fully-populated LDAP response, but if the LDAP query
transiently returns **0 groups and 0 users** (server blip, bad filter, empty
page, etc.), every existing `guacamole_entity` row looks "no longer present in
LDAP" and gets deleted.

Guacamole's own schema (`guacamole_schema.1.5.5.sql`) declares
`ON DELETE CASCADE` from several tables back to `guacamole_entity
(entity_id)`, including:

- `guacamole_user_group.entity_id`
- `guacamole_user.entity_id`
- `guacamole_user_group_member.member_entity_id`
- **`guacamole_connection_permission.entity_id`**

So deleting the entities also silently deletes every
`guacamole_connection_permission` row naming those entities — i.e. every
grant of "this user/group may use this connection". Note what is **not**
cascaded: `guacamole_connection` itself has no FK to `guacamole_entity` at
all (only to `guacamole_connection_group` via `parent_id`), so the connection
row itself is never deleted by this chain. This matters for the test design
(§4): asserting `guacamole_connection` gets "cleared" by the blip would be
asserting something the schema doesn't actually do — the real, user-visible
symptom is that the connection row survives but nobody can see/use it any
more, because its permission grants are gone.

When LDAP recovers and returns the same groups/users again,
`update_groups`/`update_users` re-`INSERT` `guacamole_entity` rows for them.
Because `entity_id` is a Postgres `serial`, the recreated rows get **new,
higher `entity_id` values**, not the ones that were deleted. Nothing in
`PostgreSQLClient` re-creates `guacamole_connection_permission` rows for the
new entity IDs — that table is never referenced anywhere in
`postgresql_client.py`. So the expected (bug) outcome is: entities come back,
but the connection permissions that pointed at the old entities do not, and
the connection stays permanently inaccessible until an admin manually
re-grants it. This is the mechanism this test should demonstrate.

## 2. Test infrastructure prerequisites

`orm.py` currently only maps `guacamole_entity`, `guacamole_user`,
`guacamole_user_group`, `guacamole_user_group_member` — enough for existing
sync logic, but not enough to set up/assert against
`guacamole_connection`/`guacamole_connection_permission`. Add two more
declarative models to `orm.py`, following the exact style of the existing
ones (plain `Mapped[...]` columns, no relationships/cascades — per the
"thin backend, no ORM relationships" design decision in `tech_stack.md`):

- `GuacamoleConnection` (`__tablename__ = "guacamole_connection"`):
  `connection_id` (PK), `connection_name`, `protocol` — the minimal
  NOT NULL columns needed to satisfy the schema; other nullable columns can
  be omitted.
- `GuacamoleConnectionPermission`
  (`__tablename__ = "guacamole_connection_permission"`): `entity_id`,
  `connection_id`, `permission`, matching the table's composite primary key.
  `permission` needs a `GuacamoleObjectPermissionType` enum (mirroring
  `GuacamoleEntityType`) with at least the `READ` member, since
  `guacamole_object_permission_type` is one of the enum columns and the ORM
  layer needs a Python-side enum to map it even though SQLite (per the
  accepted limitation in plan 01) won't enforce it.

These models are additive and read-only from the sync logic's point of view
— `PostgreSQLClient` does not need to import or use them for this task; they
exist purely so tests can arrange/assert connection-table state through the
same `PostgreSQLBackend.add_all`/`query` interface already used for
`GuacamoleEntity` fixtures, instead of hand-writing raw SQL.

## 3. Test data fixtures (`tests/conftest.py`)

Add fixtures alongside the existing `postgresql_model_guacamoleentity_*`
ones, reusing the same "Roman lawsuit" naming (`aulus.agerius`,
`plaintiffs`, etc.) already used throughout the fixture set for consistency:

- `postgresql_model_guacamoleconnection_fixture` — one or two
  `GuacamoleConnection` rows (e.g. `connection_id=1, connection_name="rome-vm-1", protocol="vnc"`).
- `postgresql_model_guacamoleconnectionpermission_fixture` — `READ`
  permission rows tying a specific user entity (from
  `postgresql_model_guacamoleentity_user_fixture`) and/or a group entity
  (from `postgresql_model_guacamoleentity_user_group_fixture`) to that
  connection.

No changes are needed to `postgresql_sqlite_backend_fixture` itself — it
already builds every table in the real schema (minus the enum `DO $$`
blocks) and applies `PRAGMA foreign_keys=ON`, which is essential here: the
cascade behaviour under test only happens if SQLite is actually enforcing
FKs.

## 4. Test flow

New test module `tests/test_synchronise.py` (there is currently no test
coverage at all for `synchronise.py`). One test class, one scenario, driving
`synchronise.synchronise()` directly — not `main()`, to avoid the infinite
`while True` loop — called twice in sequence against the *same* backend to
simulate two consecutive sync cycles:

1. **Arrange.** Using `postgresql_sqlite_backend_fixture` directly (not
   through `PostgreSQLClient`, so the test controls exactly what's in the
   database before any sync runs):
   - Insert `guacamole_entity` rows for one group and one user (via
     `postgresql_model_guacamoleentity_fixture` or a subset).
   - Insert the matching `guacamole_user_group`/`guacamole_user` rows (as
     `TestPostgreSQLBackendWithRealSchema` already does for `GuacamoleEntity`).
   - Insert one `guacamole_connection` row and one
     `guacamole_connection_permission` row granting the user's entity `READ`
     on that connection.
   - Build a `PostgreSQLClient` with dummy connection details (matching the
     `client_kwargs` pattern in `TestPostgreSQLClient`), then overwrite its
     public `.backend` attribute with `postgresql_sqlite_backend_fixture` —
     this needs no production code change, since `PostgreSQLClient.backend`
     is already a plain public attribute.
   - Build a real `LDAPClient` (dummy hostname is fine, since `connect` is
     monkeypatched, following the exact pattern already used in
     `tests/test_ldap.py`) plus `LDAPQuery` fixtures
     (`ldap_query_groups_fixture`/`ldap_query_users_fixture`).

2. **Act — simulate the blip.** `monkeypatch.setattr(LDAPClient, "connect",
   lambda self: MockLDAPConnection(server=MockLDAPServer([])))` so
   `search_groups`/`search_users` both return `[]` — i.e. LDAP answered, but
   with 0 groups and 0 users, exactly as `synchronise()` would see a blip.
   Call `synchronise.synchronise(ldap_client=..., ldap_group_query=...,
   ldap_user_query=..., postgresql_client=...)` once.

3. **Assert — tables are cleared.**
   - `backend.query(GuacamoleEntity)` is empty.
   - `backend.query(GuacamoleConnectionPermission)` is empty (cascade-deleted
     via the entity FK, per §1).
   - `backend.query(GuacamoleConnection)` still contains the original
     connection row, unchanged — explicitly asserting it is **not** cleared,
     since (per §1) nothing in the schema or sync logic touches
     `guacamole_connection` directly. Documenting this as a passing
     assertion (rather than omitting the table) makes the test's scope
     explicit and prevents a future reader from assuming the connection row
     itself was expected to disappear.

4. **Act — simulate recovery.** Re-point `LDAPClient.connect` at a
   `MockLDAPServer` populated with the *same* group/user LDAP entries used
   in step 1 (reuse `ldap_response_groups_fixture`/
   `ldap_response_users_fixture`-style data scoped to just this group/user).
   Call `synchronise.synchronise(...)` a second time with the same
   `postgresql_client`.

5. **Assert — recovery.**
   - `guacamole_entity` has the group and user back (by `name`/`type` —
     don't assert on `entity_id`, since it's a new autoincrement value, not
     the original one; asserting equality on the old ID would be asserting
     something the `serial` column doesn't guarantee).
   - `guacamole_connection` is unchanged throughout (still present, still
     the original row) — confirms this table was never at risk.
   - `guacamole_connection_permission` again grants the (new) user entity
     `READ` on the connection. **This assertion is expected to fail against
     current code** — see §1: nothing in `PostgreSQLClient` re-creates
     connection permissions. Leave the assertion as a plain, unmarked
     `assert` and let the test fail: this test is diagnostic, written to
     confirm and document the bug described in §1, not to guard against a
     regression yet. The fix is a separate follow-up change, at which point
     this test should simply start passing on its own — no `xfail` marker
     to track or later remove.

## 5. Verification

Once implemented, run `hatch run test:all` (expect the new
`test_synchronise.py` test to fail on the final assertion, documenting the
bug; everything else green) and `hatch run lint:all` before opening the PR,
per `specs/coding-guidelines.md`.
