import runpy
from typing import TYPE_CHECKING, Any, ClassVar

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

import synchronise
from guacamole_user_sync.ldap import LDAPClient
from guacamole_user_sync.models import LDAPQuery
from guacamole_user_sync.postgresql import (
    PostgreSQLBackend,
    PostgreSQLClient,
    SchemaVersion,
)
from guacamole_user_sync.postgresql.orm import (
    GuacamoleConnection,
    GuacamoleConnectionPermission,
    GuacamoleEntity,
    GuacamoleEntityType,
    GuacamoleObjectPermissionType,
    GuacamoleUser,
    GuacamoleUserGroup,
)

from .mocks import (
    MockLDAPConnection,
    MockLDAPGroupEntry,
    MockLDAPServer,
    MockLDAPUserEntry,
)

ADMIN_GROUP_NAME = "magistrates"
USER_GROUP_NAME = "plaintiffs"
GROUP_PERMISSIONS = {
    ADMIN_GROUP_NAME: [
        GuacamoleObjectPermissionType.READ,
        GuacamoleObjectPermissionType.UPDATE,
        GuacamoleObjectPermissionType.DELETE,
        GuacamoleObjectPermissionType.ADMINISTER,
    ],
    USER_GROUP_NAME: [GuacamoleObjectPermissionType.READ],
    "auditors": [GuacamoleObjectPermissionType.READ],
}
OTHER_REQUIRED_ENV_VARS: dict[str, str] = {
    "LDAP_HOST": "ldap-host",
    "LDAP_GROUP_BASE_DN": "OU=groups,DC=rome,DC=la",
    "LDAP_GROUP_FILTER": "(objectClass=posixGroup)",
    "LDAP_USER_BASE_DN": "OU=users,DC=rome,DC=la",
    "LDAP_USER_FILTER": "(objectClass=posixAccount)",
    "POSTGRESQL_HOST": "postgresql-host",
    "POSTGRESQL_PASSWORD": "postgresql-password",
    "POSTGRESQL_USERNAME": "postgresql-username",
}


def _skip_ensure_schema(_schema_version: SchemaVersion) -> None:
    """No-op: the fixture backend already has the schema built.

    `ensure_schema`'s raw commands include Postgres-only `DO $$` blocks that
    SQLite can't execute.
    """


class TestSynchroniseRecoveryAfterLDAPBlip:
    """Verify the fix for issue #2480.

    An LDAP blip still deletes connection permissions via cascade, but the
    admin/user group connection permissions are restored automatically on
    the next successful sync cycle.
    """

    client_kwargs: ClassVar[dict[str, Any]] = {
        "database_name": "database_name",
        "host_name": "host_name",
        "port": 1234,
        "user_name": "user_name",
        "user_password": "user_password",
    }

    def seed_database(  # noqa: PLR0913
        self,
        backend: PostgreSQLBackend,
        postgresql_model_guacamoleentity_user_group_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleentity_user_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleentity_admin_group_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
        postgresql_model_guacamoleusergroup_admin_fixture: list[GuacamoleUserGroup],
        postgresql_model_guacamoleuser_fixture: list[GuacamoleUser],
        postgresql_model_guacamoleconnection_fixture: list[GuacamoleConnection],
    ) -> None:
        """Seed the user/admin groups, one user, a connection, and its grant."""
        group_entity = postgresql_model_guacamoleentity_user_group_fixture[
            2
        ]  # plaintiffs
        admin_group_entity = postgresql_model_guacamoleentity_admin_group_fixture[
            0
        ]  # magistrates
        user_entity = postgresql_model_guacamoleentity_user_fixture[0]  # aulus.agerius
        backend.add_all([group_entity, admin_group_entity, user_entity])
        backend.add_all([postgresql_model_guacamoleusergroup_fixture[2]])
        backend.add_all(postgresql_model_guacamoleusergroup_admin_fixture)
        backend.add_all([postgresql_model_guacamoleuser_fixture[0]])
        backend.add_all(postgresql_model_guacamoleconnection_fixture)
        backend.add_all(
            [
                GuacamoleConnectionPermission(
                    entity_id=group_entity.entity_id,
                    connection_id=postgresql_model_guacamoleconnection_fixture[
                        0
                    ].connection_id,
                    permission=GuacamoleObjectPermissionType.READ,
                ),
            ],
        )

    def patch_ldap_connect(
        self,
        monkeypatch: pytest.MonkeyPatch,
        group_entries: list[MockLDAPGroupEntry],
        user_entries: list[MockLDAPUserEntry],
    ) -> None:
        """Make LDAPClient.connect return `group_entries`/`user_entries` in turn.

        `search_groups` and `search_users` each call `connect()` once, in
        that order, so the two connections are handed out sequentially.
        """
        connections: Iterator[MockLDAPConnection] = iter(
            [
                MockLDAPConnection(server=MockLDAPServer(group_entries)),
                MockLDAPConnection(server=MockLDAPServer(user_entries)),
            ],
        )
        monkeypatch.setattr(LDAPClient, "connect", lambda _: next(connections))

    def run_synchronise(
        self,
        ldap_client: LDAPClient,
        ldap_group_query: LDAPQuery,
        ldap_user_query: LDAPQuery,
        postgresql_client: PostgreSQLClient,
    ) -> None:
        """Run `synchronise()` with this test's group permissions mapping."""
        synchronise.synchronise(
            guacamole_group_permissions=GROUP_PERMISSIONS,
            ldap_client=ldap_client,
            ldap_group_query=ldap_group_query,
            ldap_user_query=ldap_user_query,
            postgresql_client=postgresql_client,
        )

    def test_connection_permission_restored_after_ldap_recovers(  # noqa: PLR0913
        self,
        postgresql_sqlite_backend_fixture: PostgreSQLBackend,
        postgresql_model_guacamoleentity_user_group_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleentity_user_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleentity_admin_group_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
        postgresql_model_guacamoleusergroup_admin_fixture: list[GuacamoleUserGroup],
        postgresql_model_guacamoleuser_fixture: list[GuacamoleUser],
        postgresql_model_guacamoleconnection_fixture: list[GuacamoleConnection],
        ldap_query_groups_fixture: LDAPQuery,
        ldap_query_users_fixture: LDAPQuery,
        ldap_response_groups_fixture: list[MockLDAPGroupEntry],
        ldap_response_users_fixture: list[MockLDAPUserEntry],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # --- Arrange: the user group ("plaintiffs"), the admin group
        # ("magistrates"), one user, a connection, and a READ grant for the
        # user group on that connection ---
        backend = postgresql_sqlite_backend_fixture
        self.seed_database(
            backend,
            postgresql_model_guacamoleentity_user_group_fixture,
            postgresql_model_guacamoleentity_user_fixture,
            postgresql_model_guacamoleentity_admin_group_fixture,
            postgresql_model_guacamoleusergroup_fixture,
            postgresql_model_guacamoleusergroup_admin_fixture,
            postgresql_model_guacamoleuser_fixture,
            postgresql_model_guacamoleconnection_fixture,
        )

        postgresql_client = PostgreSQLClient(**self.client_kwargs)
        postgresql_client.backend = backend
        postgresql_client.ensure_schema = _skip_ensure_schema  # type: ignore[assignment]

        ldap_client = LDAPClient("test-host", auto_bind=False)

        # --- Act: simulate a blip where LDAP returns 0 groups and 0 users ---
        self.patch_ldap_connect(monkeypatch, [], [])
        self.run_synchronise(
            ldap_client,
            ldap_query_groups_fixture,
            ldap_query_users_fixture,
            postgresql_client,
        )

        # --- Assert: entities and connection permissions are cleared, but
        # the connection row itself is untouched ---
        assert backend.query(GuacamoleEntity) == []
        assert backend.query(GuacamoleConnectionPermission) == []
        surviving_connections = backend.query(GuacamoleConnection)
        assert len(surviving_connections) == 1
        assert surviving_connections[0].connection_id == 1
        assert surviving_connections[0].connection_name == "rome-vm-1"

        # --- Act: simulate LDAP recovery, returning the user group and user
        # again (the admin group, "magistrates", does not come back) ---
        recovered_group_entries = [
            entry
            for entry in ldap_response_groups_fixture
            if entry.cn.value == USER_GROUP_NAME
        ]
        recovered_user_entries = [
            entry
            for entry in ldap_response_users_fixture
            if entry.uid.value == "aulus.agerius"
        ]
        self.patch_ldap_connect(
            monkeypatch,
            recovered_group_entries,
            recovered_user_entries,
        )
        self.run_synchronise(
            ldap_client,
            ldap_query_groups_fixture,
            ldap_query_users_fixture,
            postgresql_client,
        )

        # --- Assert: the user group/user entities come back (under new
        # entity IDs; "magistrates" does not, since LDAP didn't return it),
        # the connection is still untouched, and the connection permission
        # is restored against the recovered group's new entity_id ---
        recovered_entities = backend.query(GuacamoleEntity)
        assert {(entity.name, entity.type) for entity in recovered_entities} == {
            (USER_GROUP_NAME, GuacamoleEntityType.USER_GROUP),
            ("aulus.agerius@rome.la", GuacamoleEntityType.USER),
        }
        connections_after_recovery = backend.query(GuacamoleConnection)
        assert len(connections_after_recovery) == 1
        assert connections_after_recovery[0].connection_id == 1

        new_group_entity_id = next(
            entity.entity_id
            for entity in recovered_entities
            if entity.name == USER_GROUP_NAME
        )
        restored_permissions = backend.query(
            GuacamoleConnectionPermission,
            entity_id=new_group_entity_id,
        )
        assert len(restored_permissions) == 1
        assert restored_permissions[0].connection_id == 1
        assert restored_permissions[0].permission == GuacamoleObjectPermissionType.READ


def _fail_if_constructed(*_args: object, **_kwargs: object) -> None:
    msg = "Client constructed before GUACAMOLE_GROUP_PERMISSIONS was validated"
    raise AssertionError(msg)


class TestSynchroniseStartup:
    """Verify GUACAMOLE_GROUP_PERMISSIONS is validated before the sync loop starts."""

    def prepare_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set every other required env var and block client construction.

        This isolates the assertions below to `GUACAMOLE_GROUP_PERMISSIONS`
        validation and proves it happens before an LDAPClient/PostgreSQLClient
        is ever constructed.
        """
        for name, value in OTHER_REQUIRED_ENV_VARS.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setattr(LDAPClient, "__init__", _fail_if_constructed)
        monkeypatch.setattr(PostgreSQLClient, "__init__", _fail_if_constructed)

    def test_missing_group_permissions_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("GUACAMOLE_GROUP_PERMISSIONS", raising=False)
        self.prepare_env(monkeypatch)

        with pytest.raises(
            ValueError,
            match="GUACAMOLE_GROUP_PERMISSIONS is not defined",
        ):
            runpy.run_path(synchronise.__file__, run_name="__main__")

    def test_malformed_group_permissions_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GUACAMOLE_GROUP_PERMISSIONS", "NOT_VALID")
        self.prepare_env(monkeypatch)

        with pytest.raises(ValueError, match="missing '='"):
            runpy.run_path(synchronise.__file__, run_name="__main__")


class TestParseGroupPermissions:
    """Test `synchronise.parse_group_permissions`."""

    def test_multiple_groups(self) -> None:
        assert synchronise.parse_group_permissions(
            "admins=READ,UPDATE,DELETE,ADMINISTER;users=READ;auditors=READ",
        ) == {
            "admins": [
                GuacamoleObjectPermissionType.READ,
                GuacamoleObjectPermissionType.UPDATE,
                GuacamoleObjectPermissionType.DELETE,
                GuacamoleObjectPermissionType.ADMINISTER,
            ],
            "users": [GuacamoleObjectPermissionType.READ],
            "auditors": [GuacamoleObjectPermissionType.READ],
        }

    def test_empty_permissions_segment(self) -> None:
        assert synchronise.parse_group_permissions("auditors=") == {"auditors": []}

    def test_whitespace_and_casing_tolerance(self) -> None:
        assert synchronise.parse_group_permissions(
            " admins = read , update ; users=read;",
        ) == {
            "admins": [
                GuacamoleObjectPermissionType.READ,
                GuacamoleObjectPermissionType.UPDATE,
            ],
            "users": [GuacamoleObjectPermissionType.READ],
        }

    def test_duplicate_group_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Duplicate group name"):
            synchronise.parse_group_permissions("admins=READ;admins=UPDATE")

    def test_malformed_entry_raises(self) -> None:
        with pytest.raises(ValueError, match="missing '='"):
            synchronise.parse_group_permissions("NOT_VALID")

    def test_empty_group_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty group name"):
            synchronise.parse_group_permissions("=READ")

    def test_unknown_permission_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid permission"):
            synchronise.parse_group_permissions("admins=NOT_A_PERMISSION")
