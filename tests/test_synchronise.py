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
    GuacamoleUser,
    GuacamoleUserGroup,
)

from .mocks import (
    MockLDAPConnection,
    MockLDAPGroupEntry,
    MockLDAPServer,
    MockLDAPUserEntry,
)


def _skip_ensure_schema(_schema_version: SchemaVersion) -> None:
    """No-op: the fixture backend already has the schema built.

    `ensure_schema`'s raw commands include Postgres-only `DO $$` blocks that
    SQLite can't execute.
    """


class TestSynchroniseRecoveryAfterLDAPBlip:
    """Diagnose issue #2480.

    An LDAP blip deletes connection permissions via cascade, and LDAP
    recovery does not restore them.
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
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
        postgresql_model_guacamoleuser_fixture: list[GuacamoleUser],
        postgresql_model_guacamoleconnection_fixture: list[GuacamoleConnection],
        postgresql_model_guacamoleconnectionpermission_fixture: list[
            GuacamoleConnectionPermission
        ],
    ) -> None:
        """Seed one group, one user, and a connection grant for that user."""
        group_entity = postgresql_model_guacamoleentity_user_group_fixture[
            2
        ]  # plaintiffs
        user_entity = postgresql_model_guacamoleentity_user_fixture[0]  # aulus.agerius
        backend.add_all([group_entity, user_entity])
        backend.add_all([postgresql_model_guacamoleusergroup_fixture[2]])
        backend.add_all([postgresql_model_guacamoleuser_fixture[0]])
        backend.add_all(postgresql_model_guacamoleconnection_fixture)
        backend.add_all(postgresql_model_guacamoleconnectionpermission_fixture)

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

    def test_connection_permission_not_restored_after_ldap_recovers(  # noqa: PLR0913
        self,
        postgresql_sqlite_backend_fixture: PostgreSQLBackend,
        postgresql_model_guacamoleentity_user_group_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleentity_user_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
        postgresql_model_guacamoleuser_fixture: list[GuacamoleUser],
        postgresql_model_guacamoleconnection_fixture: list[GuacamoleConnection],
        postgresql_model_guacamoleconnectionpermission_fixture: list[
            GuacamoleConnectionPermission
        ],
        ldap_query_groups_fixture: LDAPQuery,
        ldap_query_users_fixture: LDAPQuery,
        ldap_response_groups_fixture: list[MockLDAPGroupEntry],
        ldap_response_users_fixture: list[MockLDAPUserEntry],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # --- Arrange: one group, one user, and a connection grant for that
        # user, inserted directly against the SQLite-backed schema fixture ---
        backend = postgresql_sqlite_backend_fixture
        self.seed_database(
            backend,
            postgresql_model_guacamoleentity_user_group_fixture,
            postgresql_model_guacamoleentity_user_fixture,
            postgresql_model_guacamoleusergroup_fixture,
            postgresql_model_guacamoleuser_fixture,
            postgresql_model_guacamoleconnection_fixture,
            postgresql_model_guacamoleconnectionpermission_fixture,
        )

        postgresql_client = PostgreSQLClient(**self.client_kwargs)
        postgresql_client.backend = backend
        postgresql_client.ensure_schema = _skip_ensure_schema  # type: ignore[assignment]

        ldap_client = LDAPClient("test-host", auto_bind=False)

        # --- Act: simulate a blip where LDAP returns 0 groups and 0 users ---
        self.patch_ldap_connect(monkeypatch, [], [])
        synchronise.synchronise(
            ldap_client=ldap_client,
            ldap_group_query=ldap_query_groups_fixture,
            ldap_user_query=ldap_query_users_fixture,
            postgresql_client=postgresql_client,
        )

        # --- Assert: entities and connection permissions are cleared, but
        # the connection row itself is untouched ---
        assert backend.query(GuacamoleEntity) == []
        assert backend.query(GuacamoleConnectionPermission) == []
        surviving_connections = backend.query(GuacamoleConnection)
        assert len(surviving_connections) == 1
        assert surviving_connections[0].connection_id == 1
        assert surviving_connections[0].connection_name == "rome-vm-1"

        # --- Act: simulate LDAP recovery, returning the same group/user ---
        recovered_group_entries = [
            entry
            for entry in ldap_response_groups_fixture
            if entry.cn.value == "plaintiffs"
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
        synchronise.synchronise(
            ldap_client=ldap_client,
            ldap_group_query=ldap_query_groups_fixture,
            ldap_user_query=ldap_query_users_fixture,
            postgresql_client=postgresql_client,
        )

        # --- Assert: the group/user entities come back (under new entity
        # IDs), the connection is still untouched, but the connection
        # permission is not restored ---
        recovered_entities = backend.query(GuacamoleEntity)
        assert {(entity.name, entity.type) for entity in recovered_entities} == {
            ("plaintiffs", GuacamoleEntityType.USER_GROUP),
            ("aulus.agerius@rome.la", GuacamoleEntityType.USER),
        }
        connections_after_recovery = backend.query(GuacamoleConnection)
        assert len(connections_after_recovery) == 1
        assert connections_after_recovery[0].connection_id == 1

        new_user_entity_id = next(
            entity.entity_id
            for entity in recovered_entities
            if entity.name == "aulus.agerius@rome.la"
        )
        # Expected to fail against current code: issue #2480, connection
        # permissions are cascade-deleted by an LDAP blip and never restored.
        restored_permissions = backend.query(
            GuacamoleConnectionPermission,
            entity_id=new_user_entity_id,
        )
        assert restored_permissions
