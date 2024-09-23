import logging
from typing import Any, ClassVar
from unittest import mock

from sqlalchemy import text
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.engine import URL, Engine  # type: ignore
from sqlalchemy.pool.impl import QueuePool
from sqlalchemy.sql import Delete, Insert

from guacamole_user_sync.models import LDAPGroup, LDAPUser
from guacamole_user_sync.postgresql import PostgreSQLBackend, PostgreSQLClient
from guacamole_user_sync.postgresql.orm import (
    GuacamoleEntity,
    GuacamoleUser,
    GuacamoleUserGroup,
    guacamole_entity_type,
)
from guacamole_user_sync.postgresql.sql import SchemaVersion

from .mocks import MockPostgreSQLBackend, MockPostgreSQLEngine


class TestPostgreSQLBackend:
    def backend(self, *, engine: Any | None = None) -> PostgreSQLBackend:
        backend = PostgreSQLBackend(
            database_name="database_name",
            host_name="host_name",
            port=1234,
            user_name="user_name",
            user_password="user_password",
        )
        if engine:
            backend._engine = engine
        return backend

    def test_constructor(self) -> None:
        backend = self.backend()
        assert isinstance(backend, PostgreSQLBackend)
        assert backend.database_name == "database_name"
        assert backend.host_name == "host_name"
        assert backend.port == 1234
        assert backend.user_name == "user_name"
        assert backend.user_password == "user_password"

    def test_engine(self) -> None:
        backend = self.backend()
        assert isinstance(backend.engine, Engine)
        assert isinstance(backend.engine.pool, QueuePool)
        assert isinstance(backend.engine.dialect, PGDialect_psycopg)
        assert isinstance(backend.engine.url, URL)
        assert backend.engine.logging_name is None
        assert not backend.engine.echo
        assert not backend.engine.hide_parameters  # type: ignore

    def test_add_all(
        self,
        postgresql_model_guacamoleentity_fixture: list[GuacamoleEntity],
    ) -> None:
        backend = self.backend(engine=MockPostgreSQLEngine())
        backend.add_all(postgresql_model_guacamoleentity_fixture)

        # Check method calls
        backend.engine.connect_method.execute.assert_called()  # type: ignore
        backend.engine.connect_method.close.assert_called_once()  # type: ignore

        # Check method arguments
        execute_args = (
            backend.engine.connect_method.execute.call_args.args  # type: ignore
        )
        assert len(execute_args) == 2
        assert isinstance(execute_args[0], Insert)
        assert len(execute_args[1]) == len(postgresql_model_guacamoleentity_fixture)

    def test_delete(
        self,
    ) -> None:
        backend = self.backend(engine=MockPostgreSQLEngine())
        backend.delete(GuacamoleEntity)

        # Check method calls
        backend.engine.connect_method.execute.assert_called()  # type: ignore
        backend.engine.connect_method.close.assert_called_once()  # type: ignore

        # Check method arguments
        execute_args = (
            backend.engine.connect_method.execute.call_args.args  # type: ignore
        )
        assert len(execute_args) == 2
        assert isinstance(execute_args[0], Delete)
        assert isinstance(execute_args[1], dict) and len(execute_args[1]) == 0

    def test_delete_with_filter(
        self,
    ) -> None:
        backend = self.backend(engine=MockPostgreSQLEngine())
        backend.delete(
            GuacamoleEntity,
            GuacamoleEntity.type == guacamole_entity_type.USER
        )

        # Check method calls
        backend.engine.connect_method.execute.assert_called()  # type: ignore
        backend.engine.connect_method.close.assert_called_once()  # type: ignore

        # Check method arguments
        execute_args = (
            backend.engine.connect_method.execute.call_args.args  # type: ignore
        )
        assert len(execute_args) == 2
        assert isinstance(execute_args[0], Delete)
        assert isinstance(execute_args[1], dict) and len(execute_args[1]) == 0


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
        postgresql_model_guacamoleentity_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend"
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = MockPostgreSQLBackend(
                query_results={
                    GuacamoleEntity: [
                        [entity] for entity in postgresql_model_guacamoleentity_fixture
                    ],
                    GuacamoleUserGroup: [
                        [usergroup]
                        for usergroup in postgresql_model_guacamoleusergroup_fixture
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

    def test_assign_users_to_groups_missing_user(
        self,
        caplog: Any,
        ldap_model_groups_fixture: list[LDAPGroup],
        ldap_model_users_fixture: list[LDAPUser],
        postgresql_model_guacamoleentity_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend"
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = MockPostgreSQLBackend(
                query_results={
                    GuacamoleEntity: [
                        [entity] for entity in postgresql_model_guacamoleentity_fixture
                    ],
                    GuacamoleUserGroup: [
                        [usergroup]
                        for usergroup in postgresql_model_guacamoleusergroup_fixture
                    ],
                }
            )

            client = PostgreSQLClient(**self.client_kwargs)
            client.assign_users_to_groups(
                ldap_model_groups_fixture, ldap_model_users_fixture[0:1]
            )
            for output_line in (
                "Ensuring that 1 user(s) are correctly assigned among 3 group(s)",
                "Could not find user with UID numerius.negidius",
                "... creating 2 user/group assignments",
            ):
                assert output_line in caplog.text

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

    def test_update_groups(
        self,
        caplog: Any,
        ldap_model_groups_fixture: list[LDAPGroup],
        postgresql_model_guacamoleentity_USER_GROUP_fixture: list[GuacamoleEntity],
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend"
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = MockPostgreSQLBackend(
                query_results={
                    GuacamoleEntity: [
                        postgresql_model_guacamoleentity_USER_GROUP_fixture[0:1]
                        + [
                            GuacamoleEntity(
                                entity_id=99,
                                name="to-be-deleted",
                                type=guacamole_entity_type.USER_GROUP,
                            )
                        ],
                    ]
                }
            )

            client = PostgreSQLClient(**self.client_kwargs)
            client.update_groups(ldap_model_groups_fixture)
            assert "Ensuring that 3 group(s) are registered" in caplog.text
            assert "There are 2 group(s) currently registered" in caplog.text
            assert "... 2 group(s) will be added" in caplog.text
            assert "... 1 group(s) will be removed" in caplog.text

    def test_update_group_entities(
        self,
        caplog: Any,
        postgresql_model_guacamoleentity_USER_GROUP_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend"
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = MockPostgreSQLBackend(
                query_results={
                    GuacamoleEntity: [
                        postgresql_model_guacamoleentity_USER_GROUP_fixture,
                        postgresql_model_guacamoleentity_USER_GROUP_fixture,
                    ],
                    GuacamoleUserGroup: [
                        postgresql_model_guacamoleusergroup_fixture[0:1]
                    ],
                }
            )

            client = PostgreSQLClient(**self.client_kwargs)
            client.update_group_entities()
            for output_line in (
                "There are 1 user group entit(y|ies) currently registered",
                "... 2 user group entit(y|ies) will be added",
                "There are 3 valid user group entit(y|ies)",
            ):
                assert output_line in caplog.text

    def test_update_users(
        self,
        caplog: Any,
        ldap_model_users_fixture: list[LDAPUser],
        postgresql_model_guacamoleentity_USER_fixture: list[GuacamoleEntity],
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend"
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = MockPostgreSQLBackend(
                query_results={
                    GuacamoleEntity: [
                        postgresql_model_guacamoleentity_USER_fixture[0:1]
                        + [
                            GuacamoleEntity(
                                entity_id=99,
                                name="to-be-deleted",
                                type=guacamole_entity_type.USER,
                            )
                        ],
                    ]
                }
            )

            client = PostgreSQLClient(**self.client_kwargs)
            client.update_users(ldap_model_users_fixture)
            assert "Ensuring that 2 user(s) are registered" in caplog.text
            assert "There are 2 user(s) currently registered" in caplog.text
            assert "... 1 user(s) will be added" in caplog.text
            assert "... 1 user(s) will be removed" in caplog.text

    def test_update_user_entities(
        self,
        caplog: Any,
        ldap_model_users_fixture: list[LDAPUser],
        postgresql_model_guacamoleuser_fixture: list[GuacamoleUser],
        postgresql_model_guacamoleentity_USER_fixture: list[GuacamoleEntity],
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend"
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = MockPostgreSQLBackend(
                query_results={
                    GuacamoleEntity: [
                        postgresql_model_guacamoleentity_USER_fixture,
                        postgresql_model_guacamoleentity_USER_fixture,
                    ],
                    GuacamoleUser: [postgresql_model_guacamoleuser_fixture[0:1]],
                }
            )

            client = PostgreSQLClient(**self.client_kwargs)
            client.update_user_entities(ldap_model_users_fixture)
            for output_line in (
                "There are 1 user entit(y|ies) currently registered",
                "... 1 user entit(y|ies) will be added",
                "There are 2 valid user entit(y|ies)",
            ):
                assert output_line in caplog.text
