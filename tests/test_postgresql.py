import logging
from typing import Any
from unittest import mock

from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.engine import URL, Engine  # type: ignore
from sqlalchemy.pool.impl import QueuePool

from guacamole_user_sync.models import LDAPGroup, LDAPUser
from guacamole_user_sync.postgresql import PostgreSQLBackend, PostgreSQLClient
from guacamole_user_sync.postgresql.orm import GuacamoleEntity, GuacamoleUserGroup

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
    def test_constructor(self) -> None:
        client = PostgreSQLClient(
            database_name="database_name",
            host_name="host_name",
            port=1234,
            user_name="user_name",
            user_password="user_password",
        )
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

            client = PostgreSQLClient(
                database_name="database_name",
                host_name="host_name",
                port=1234,
                user_name="user_name",
                user_password="user_password",
            )

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
