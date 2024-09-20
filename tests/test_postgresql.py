import logging
from typing import Any, ClassVar
from unittest import mock

from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.engine import URL, Engine  # type: ignore
from sqlalchemy.pool.impl import QueuePool

from guacamole_user_sync.models import LDAPGroup, LDAPUser
from guacamole_user_sync.postgresql import PostgreSQLBackend, PostgreSQLClient
from guacamole_user_sync.postgresql.orm import GuacamoleEntity, GuacamoleUserGroup
from guacamole_user_sync.postgresql.sql import SchemaVersion

from .mocks import MockPostgreSQLBackend


class TestPostgreSQLBackend:
    backend = PostgreSQLBackend(
        database_name="database_name",
        host_name="host_name",
        port=1234,
        user_name="user_name",
        user_password="user_password",
    )

    def test_constructor(self) -> None:
        assert isinstance(self.backend, PostgreSQLBackend)
        assert self.backend.database_name == "database_name"
        assert self.backend.host_name == "host_name"
        assert self.backend.port == 1234
        assert self.backend.user_name == "user_name"
        assert self.backend.user_password == "user_password"

    def test_engine(self) -> None:
        assert isinstance(self.backend.engine, Engine)
        assert isinstance(self.backend.engine.pool, QueuePool)
        assert isinstance(self.backend.engine.dialect, PGDialect_psycopg)
        assert isinstance(self.backend.engine.url, URL)
        assert self.backend.engine.logging_name is None
        assert not self.backend.engine.echo
        assert not self.backend.engine.hide_parameters  # type: ignore


class TestPostgreSQLClient:
    client_kwargs: ClassVar[dict[str, Any]] = {
        "database_name": "database_name",
        "host_name": "host_name",
        "port": 1234,
        "user_name": "user_name",
        "user_password": "user_password",
    }

    def test_constructor(self) -> None:
        client = PostgreSQLClient(**self.client_kwargs)
        assert isinstance(client, PostgreSQLClient)
        assert isinstance(client.backend, PostgreSQLBackend)

    def test_assign_users_to_groups(
        self,
        caplog: Any,
        ldap_model_groups_fixture: list[LDAPGroup],
        ldap_model_users_fixture: list[LDAPUser],
        postgresql_model_guacamole_entity_groups_fixture: list[GuacamoleEntity],
        postgresql_model_guacamole_user_groups_fixture: list[GuacamoleUserGroup],
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend"
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = MockPostgreSQLBackend(
                query_results={
                    GuacamoleEntity: [
                        [entity]
                        for entity in postgresql_model_guacamole_entity_groups_fixture
                    ],
                    GuacamoleUserGroup: [
                        [usergroup]
                        for usergroup in postgresql_model_guacamole_user_groups_fixture
                    ],
                }
            )

            client = PostgreSQLClient(**self.client_kwargs)
            client.assign_users_to_groups(
                ldap_model_groups_fixture, ldap_model_users_fixture
            )
            assert (
                "Ensuring that 2 user(s) are correctly assigned among 3 group(s)"
                in caplog.text
            )
            assert "Working on group 'defendants'" in caplog.text
            assert "Working on group 'everyone'" in caplog.text
            assert "Working on group 'plaintiffs'" in caplog.text

    def test_ensure_schema(self, capsys: Any) -> None:
        # caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend"
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = MockPostgreSQLBackend(
                query_results={}
            )

            client = PostgreSQLClient(**self.client_kwargs)
            client.ensure_schema(SchemaVersion.v1_5_5)
            captured = capsys.readouterr()
            for type_name in (
                "guacamole_connection_group_type",
                "guacamole_entity_type",
                "guacamole_object_permission_type",
                "guacamole_system_permission_type",
                "guacamole_proxy_encryption_method",
            ):
                assert (
                    f"Executing DO $$ BEGIN\n  CREATE TYPE {type_name}" in captured.out
                )
            for table_name in (
                "guacamole_connection_group",
                "guacamole_connection",
                "guacamole_entity",
                "guacamole_user",
                "guacamole_user_group",
                "guacamole_user_group_member",
                "guacamole_sharing_profile",
                "guacamole_connection_parameter",
                "guacamole_sharing_profile_parameter",
                "guacamole_user_attribute",
                "guacamole_user_group_attribute",
                "guacamole_connection_attribute",
                "guacamole_connection_group_attribute",
                "guacamole_sharing_profile_attribute",
                "guacamole_connection_permission",
                "guacamole_connection_group_permission",
                "guacamole_sharing_profile_permission",
                "guacamole_system_permission",
                "guacamole_user_permission",
                "guacamole_user_group_permission",
                "guacamole_connection_history",
                "guacamole_user_history",
                "guacamole_user_password_history",
            ):
                assert (
                    f"Executing CREATE TABLE IF NOT EXISTS {table_name}" in captured.out
                )
            for index_name in (
                "guacamole_connection_group_parent_id",
                "guacamole_connection_parent_id",
                "guacamole_sharing_profile_primary_connection_id",
                "guacamole_connection_parameter_connection_id",
                "guacamole_sharing_profile_parameter_sharing_profile_id",
                "guacamole_user_attribute_user_id",
                "guacamole_user_group_attribute_user_group_id",
                "guacamole_connection_attribute_connection_id",
                "guacamole_connection_group_attribute_connection_group_id",
                "guacamole_sharing_profile_attribute_sharing_profile_id",
                "guacamole_connection_permission_connection_id",
                "guacamole_connection_permission_entity_id",
                "guacamole_connection_group_permission_connection_group_id",
                "guacamole_connection_group_permission_entity_id",
                "guacamole_sharing_profile_permission_sharing_profile_id",
                "guacamole_sharing_profile_permission_entity_id",
                "guacamole_system_permission_entity_id",
                "guacamole_user_permission_affected_user_id",
                "guacamole_user_permission_entity_id",
                "guacamole_user_group_permission_affected_user_group_id",
                "guacamole_user_group_permission_entity_id",
                "guacamole_connection_history_user_id",
                "guacamole_connection_history_connection_id",
                "guacamole_connection_history_sharing_profile_id",
                "guacamole_connection_history_start_date",
                "guacamole_connection_history_end_date",
                "guacamole_connection_history_connection_id_start_date",
                "guacamole_user_history_user_id",
                "guacamole_user_history_start_date",
                "guacamole_user_history_end_date",
                "guacamole_user_history_user_id_start_date",
                "guacamole_user_password_history_user_id",
            ):
                assert (
                    f"Executing CREATE INDEX IF NOT EXISTS {index_name}" in captured.out
                )
