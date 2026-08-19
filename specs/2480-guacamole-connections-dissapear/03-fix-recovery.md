# Plan

## Fix: declaratively (re-)grant connection permissions to an admin group and a user group

**Goal:** fix the bug demonstrated by
`specs/2480-guacamole-connections-dissapear/02-test-recovery.md`'s
`tests/test_synchronise.py::TestSynchroniseRecoveryAfterLDAPBlip` test, so its
final (currently failing) assertion passes — without an `xfail` marker to
remove later, per that plan's §5. Implementation must follow
`specs/coding-guidelines.md` (precise types, brief docstrings/comments,
verify with `hatch run test:all` / `hatch run lint:all`) and the conventions
in `specs/tech_stack.md`. This fix ships as release **v0.7.1**; the version
bump and Docker release process are planned separately in
`specs/2480-guacamole-connections-dissapear/04-release-fix.md`.

**This supersedes the previous revision of this plan**, which proposed
skipping the sync cycle whenever LDAP returned zero groups and zero users
(a *preventive* fix). That approach is dropped entirely: it only ever
protects against one specific trigger (a total 0-groups-and-0-users blip)
and does nothing to repair permissions already lost — either before this
fix ships, or via any other path that deletes and re-creates an entity
(the underlying `entity_id` instability described in `02-test-recovery.md`
§1 isn't specific to blips). It's replaced with a *restorative*, always-on
reconciliation step that re-derives the connection permissions that matter
from current group membership on every sync cycle, so they heal themselves
regardless of how or why they were lost.

## 1. New behaviour

Two Guacamole/LDAP groups are given a standing role by this tool:

- **Admin group** — its members should have full control of every
  Guacamole connection: `READ`, `UPDATE`, `DELETE`, and `ADMINISTER`.
- **User group** — its members should have basic access to every
  connection: `READ` only.

Guacamole itself resolves effective permissions for a user by combining
permissions granted directly to their `USER` entity *and* permissions
granted to any `USER_GROUP` entity they belong to (via
`guacamole_user_group_member`) — granting connection permissions is not
restricted to individual users. So rather than granting permissions per
member (which would require walking membership and would still break the
same way individual entities do), this tool grants permissions once, to the
**group entity** itself, for every `guacamole_connection` row. This is:

- **Self-healing.** Group membership (`guacamole_user_group_member`) is
  already reconciled every cycle by `assign_users_to_groups`; granting to
  the group entity means every current and future member benefits
  immediately, with no per-user bookkeeping.
- **Robust to `entity_id` churn.** Every cycle, the group's *current*
  `entity_id` is looked up by name — whatever it is that cycle — so even if
  the group entity was deleted and recreated (e.g. after an LDAP blip,
  exactly as `02-test-recovery.md` describes), the very next successful
  cycle re-grants the correct permissions against the new `entity_id`. This
  is what "restores the missing records" in practice: nothing needs to be
  remembered across cycles, because the desired state is always
  recomputed from scratch (consistent with the existing "Idempotent,
  declarative sync" design decision in `tech_stack.md`).

**Deliberate scope/behaviour change to flag in the PR description:** this
tool now *owns* the connection permissions of these two named groups,
exactly as specified above, on every cycle. Any other manually-granted
`guacamole_connection_permission` row — for an individual user, for a
different group, or a different permission on the admin/user group itself
(e.g. someone manually grants `UPDATE` to the user group in the Guacamole
UI) — is left untouched **except** for extra permissions on the admin/user
group entities themselves, which are actively removed to enforce the
"admin gets exactly these four, user gets exactly `READ`" contract (see
§3). This is a superset of "restore what's missing"; it's necessary to keep
the invariant true in general, not just after a blip.

## 2. New environment variables

Following the existing `LDAP_*`/`POSTGRESQL_*` fail-fast-if-missing
convention in `synchronise.py`'s `if __name__ == "__main__":` block:

- `GUACAMOLE_ADMIN_GROUP_NAME` — name of the LDAP group whose members get
  full connection control. **Required** (raise `ValueError` at startup if
  unset, matching `LDAP_GROUP_BASE_DN` et al.).
- `GUACAMOLE_USER_GROUP_NAME` — name of the LDAP group whose members get
  read-only connection access. **Required**, same rationale.

Both names must exactly match a group name as returned by the existing
`LDAP_GROUP_FILTER`/`LDAP_GROUP_NAME_ATTR` query — i.e. the group must
already be one of the groups this tool syncs into `guacamole_entity`. If a
name doesn't match any currently-synced group (typo, wrong base DN, or a
transient cycle where that group didn't come back yet), log a `WARNING` and
skip granting for that group *this cycle* — don't raise, since this is
exactly the "expected to self-heal on a later cycle" case, not a fatal
misconfiguration once the name is confirmed correct at least once. Document
this prerequisite in `README.md` alongside the new variables.

## 3. Implementation

### 3.1 `guacamole_user_sync/postgresql/postgresql_client.py`

Import `GuacamoleConnection`, `GuacamoleConnectionPermission`, and
`GuacamoleObjectPermissionType` from `.orm` (already defined there per
`02-test-recovery.md` §2). Add two module-level constants and one public +
one private method:

```python
ADMIN_CONNECTION_PERMISSIONS = [
    GuacamoleObjectPermissionType.READ,
    GuacamoleObjectPermissionType.UPDATE,
    GuacamoleObjectPermissionType.DELETE,
    GuacamoleObjectPermissionType.ADMINISTER,
]
USER_CONNECTION_PERMISSIONS = [GuacamoleObjectPermissionType.READ]
```

```python
def ensure_connection_permissions(
    self,
    *,
    admin_group_name: str,
    user_group_name: str,
) -> None:
    """Grant the admin/user groups their standing permissions on every connection."""
    self._reconcile_group_connection_permissions(
        admin_group_name,
        ADMIN_CONNECTION_PERMISSIONS,
    )
    self._reconcile_group_connection_permissions(
        user_group_name,
        USER_CONNECTION_PERMISSIONS,
    )

def _reconcile_group_connection_permissions(
    self,
    group_name: str,
    permissions: list[GuacamoleObjectPermissionType],
) -> None:
    """Make one group's connection grants match `permissions` on every connection."""
    try:
        entity_id = next(
            entity.entity_id
            for entity in self.backend.query(
                GuacamoleEntity,
                name=group_name,
                type=GuacamoleEntityType.USER_GROUP,
            )
        )
    except StopIteration:
        logger.warning(
            "Could not find group '%s': skipping its connection permissions "
            "this cycle.",
            group_name,
        )
        return

    connection_ids = [
        connection.connection_id
        for connection in self.backend.query(GuacamoleConnection)
    ]
    desired = {
        (connection_id, permission)
        for connection_id in connection_ids
        for permission in permissions
    }
    current = {
        (grant.connection_id, grant.permission)
        for grant in self.backend.query(
            GuacamoleConnectionPermission,
            entity_id=entity_id,
        )
    }
    self.backend.add_all(
        [
            GuacamoleConnectionPermission(
                entity_id=entity_id,
                connection_id=connection_id,
                permission=permission,
            )
            for connection_id, permission in desired - current
        ],
    )
    for connection_id, permission in current - desired:
        self.backend.delete(
            GuacamoleConnectionPermission,
            GuacamoleConnectionPermission.entity_id == entity_id,
            GuacamoleConnectionPermission.connection_id == connection_id,
            GuacamoleConnectionPermission.permission == permission,
        )
```

Computing `desired - current` and only inserting the difference is what
satisfies "if the required information is already there, don't fail": the
composite primary key (`entity_id`, `connection_id`, `permission`) is never
re-inserted for a grant that already exists, so there's no
`IntegrityError`/`SQLAlchemyError` to handle — this mirrors the existing
add/remove-diff pattern already used by `update_groups`/`update_users`/
`update_group_entities`, rather than introducing new error handling.

Call it from `update()`, after everything else (permissions should reflect
the *result* of this cycle's entity/membership reconciliation, not a
snapshot from before it):

```python
def update(
    self,
    *,
    groups: list[LDAPGroup],
    users: list[LDAPUser],
    guacamole_admin_group_name: str,
    guacamole_user_group_name: str,
) -> None:
    """Update the relevant tables to match lists of LDAP users and groups."""
    self.update_groups(groups)
    self.update_users(users)
    self.update_group_entities()
    self.update_user_entities(users)
    self.assign_users_to_groups(groups, users)
    self.ensure_connection_permissions(
        admin_group_name=guacamole_admin_group_name,
        user_group_name=guacamole_user_group_name,
    )
```

No changes to `update_groups`/`update_users`/`update_group_entities`/
`update_user_entities`/`assign_users_to_groups` themselves, and no changes
to `orm.py` (the models already exist).

### 3.2 `synchronise.py`

Thread the two names through, the same way `ldap_group_query`/
`ldap_user_query` are already threaded from `main()` into `synchronise()`:

- `synchronise()` gains `guacamole_admin_group_name: str` and
  `guacamole_user_group_name: str` keyword-only parameters, passed straight
  through to `postgresql_client.update(...)`.
- `main()` gains the same two parameters, passed straight through to
  `synchronise(...)` inside the loop.
- The `if __name__ == "__main__":` block reads the two new required env
  vars (§2) alongside the existing `LDAP_*`/`POSTGRESQL_*` ones, and passes
  them into `main(...)`.

### 3.3 `README.md`

Add `GUACAMOLE_ADMIN_GROUP_NAME` and `GUACAMOLE_USER_GROUP_NAME` to the
environment variable list (alongside the existing `LDAP_*` entries) and to
the example `docker run`/compose snippets, with the prerequisite from §2
(the name must match a group already covered by `LDAP_GROUP_BASE_DN`/
`LDAP_GROUP_FILTER`) called out explicitly.

## 4. Test changes

### 4.1 `tests/conftest.py`

Add a group to `postgresql_model_guacamoleentity_user_group_fixture` (or a
new fixture) representing the admin role — reuse the Roman-lawsuit theme,
e.g. a `magistrates` group (`entity_id=6`) alongside the existing
`plaintiffs` group, which already fits naturally as the "user group" for
tests (it has one member, `aulus.agerius`, already wired up through
`postgresql_model_guacamoleusergroup_fixture`/
`ldap_model_groups_fixture`/`ldap_response_groups_fixture`). Add the
matching `GuacamoleUserGroup` row for `magistrates`'s `entity_id`.

No separate unit tests for `ensure_connection_permissions`/
`_reconcile_group_connection_permissions` in `tests/test_postgresql.py` —
per `specs/coding-guidelines.md`'s testing guidance, `tests/test_synchronise.py`
(§4.2 below) already drives this method end-to-end twice (once per
`synchronise()` call), covering both the idempotent-add path and the
missing-group warning path (the admin/user groups are deleted by the blip
before `ensure_connection_permissions` runs in that same cycle, so the
`StopIteration`/warning branch is exercised naturally). A separate test
module hitting the same method directly would just re-test paths the
existing suite already covers.

### 4.2 `tests/test_synchronise.py`

Update `TestSynchroniseRecoveryAfterLDAPBlip` so the scenario matches the
new mechanism instead of the old per-user-entity permission fixture:

- Seed the `plaintiffs` group as the configured user group and the new
  `magistrates` group as the configured admin group; drop the direct
  user-entity permission grant from `postgresql_model_guacamoleconnectionpermission_fixture`
  in favour of connection permissions granted to the `plaintiffs`/
  `magistrates` group entities (via the same reconciliation method, called
  once up front to seed "pre-blip" state, or via a fixture that constructs
  the rows directly — whichever keeps the arrange step simplest).
- Pass `guacamole_admin_group_name="magistrates"` and
  `guacamole_user_group_name="plaintiffs"` into every `synchronise()` call.
- After the first `synchronise()` call (LDAP blip: 0 groups, 0 users): keep
  the existing assertions that `GuacamoleEntity` and
  `GuacamoleConnectionPermission` are wiped, and `GuacamoleConnection`
  survives — this part of the mechanism (§1 of `02-test-recovery.md`) is
  unchanged; the blip still deletes entities exactly as before.
- After the second `synchronise()` call (LDAP recovers with the same
  group/user data): assert the `plaintiffs` group's **new** `entity_id` now
  has a `READ` grant on the connection again. This is the assertion that
  was previously expected to fail — with `ensure_connection_permissions`
  now running unconditionally at the end of every `update()`, it passes
  because the permission is re-derived from the recovered group's current
  `entity_id`, not carried over from the deleted row.
- Rename the test to reflect the fix, e.g.
  `test_connection_permission_restored_after_ldap_recovers`, and update the
  class/method docstrings accordingly (no longer "diagnose issue #2480" —
  it now verifies the fix).

## 5. Verification

Once implemented, run `hatch run test:all` (expect
`test_synchronise.py::TestSynchroniseRecoveryAfterLDAPBlip` to pass, with no
`xfail`/skip markers anywhere) and `hatch run lint:all` before opening the
PR, per `specs/coding-guidelines.md`. Confirm the PR description calls out:

- The new required env vars (`GUACAMOLE_ADMIN_GROUP_NAME`,
  `GUACAMOLE_USER_GROUP_NAME`) and the prerequisite that they must name a
  group already covered by the existing LDAP group query — deployments
  upgrading need their environment updated, or the app will fail fast at
  startup.
- The behaviour change from §1: this tool now actively enforces (adds
  *and* removes) connection permissions for these two groups on every
  cycle, superseding any manually-granted permissions on those specific
  group entities.

The version bump and Docker release for this fix are covered separately in
`specs/2480-guacamole-connections-dissapear/04-release-fix.md`.
