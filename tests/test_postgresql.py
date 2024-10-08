import logging
from typing import Any, ClassVar
from unittest import mock

import pytest
from sqlalchemy import URL, Engine, text
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.sql.elements import BinaryExpression, TextClause

from guacamole_user_sync.models import LDAPGroup, LDAPUser, PostgreSQLError
from guacamole_user_sync.postgresql import (
    PostgreSQLBackend,
    PostgreSQLClient,
    PostgreSQLConnectionDetails,
)
from guacamole_user_sync.postgresql.orm import (
    GuacamoleEntity,
    GuacamoleEntityType,
    GuacamoleUser,
    GuacamoleUserGroup,
)
from guacamole_user_sync.postgresql.sql import SchemaVersion

from .mocks import MockPostgreSQLBackend


class TestPostgreSQLBackend:
    """Test PostgreSQLBackend."""

    def mock_backend(self, session: Session | None = None) -> PostgreSQLBackend:
        return PostgreSQLBackend(
            connection_details=PostgreSQLConnectionDetails(
                database_name="database_name",
                host_name="host_name",
                port=1234,
                user_name="user_name",
                user_password="user_password",  # noqa: S106
            ),
            session=session,
        )

    def mock_session(self) -> mock.MagicMock:
        mock_session = mock.MagicMock()
        mock_session.__enter__.return_value = mock_session
        mock_session.filter.return_value = mock_session
        mock_session.query.return_value = mock_session
        return mock_session

    def test_constructor(self) -> None:
        backend = self.mock_backend()
        assert isinstance(backend, PostgreSQLBackend)
        assert isinstance(backend.connection_details, PostgreSQLConnectionDetails)
        assert backend.connection_details.database_name == "database_name"
        assert backend.connection_details.host_name == "host_name"
        assert backend.connection_details.port == 1234  # noqa: PLR2004
        assert backend.connection_details.user_name == "user_name"
        assert backend.connection_details.user_password == "user_password"  # noqa: S105

    def test_engine(self) -> None:
        backend = self.mock_backend()
        assert isinstance(backend.engine, Engine)
        assert isinstance(backend.engine.pool, QueuePool)
        assert isinstance(backend.engine.dialect, PGDialect_psycopg)
        assert isinstance(backend.engine.url, URL)
        assert backend.engine.logging_name is None
        assert not backend.engine.echo
        assert not backend.engine.hide_parameters

    def test_session(self) -> None:
        backend = self.mock_backend()
        assert isinstance(backend.session(), Session)

    def test_add_all(
        self,
        postgresql_model_guacamoleentity_fixture: list[GuacamoleEntity],
    ) -> None:
        session = self.mock_session()
        backend = self.mock_backend(session=session)
        backend.add_all(postgresql_model_guacamoleentity_fixture)

        # Check method calls
        session.add_all.assert_called_once()
        session.__exit__.assert_called_once()

        # Check method arguments
        execute_args = session.add_all.call_args.args
        assert len(execute_args) == 1
        assert len(execute_args[0]) == len(postgresql_model_guacamoleentity_fixture)

    def test_delete(self) -> None:
        session = self.mock_session()
        backend = self.mock_backend(session=session)
        backend.delete(GuacamoleEntity)

        # Check method calls
        session.query.assert_called_once()
        session.filter.assert_not_called()
        session.delete.assert_called_once()
        session.__exit__.assert_called_once()

        # Check method arguments
        query_args = session.query.call_args.args
        assert len(query_args) == 1
        assert isinstance(query_args[0], type(GuacamoleEntity))

    def test_delete_with_filter(self) -> None:
        session = self.mock_session()
        backend = self.mock_backend(session=session)
        backend.delete(
            GuacamoleEntity,
            GuacamoleEntity.type == GuacamoleEntityType.USER,
        )

        # Check method calls
        session.query.assert_called_once()
        session.filter.assert_called_once()
        session.delete.assert_called_once()
        session.__exit__.assert_called_once()

        # Check method arguments
        query_args = session.query.call_args.args
        assert len(query_args) == 1
        assert isinstance(query_args[0], type(GuacamoleEntity))
        filter_args = session.filter.call_args.args
        assert len(filter_args) == 1
        assert isinstance(filter_args[0], BinaryExpression)

    def test_execute_commands(self) -> None:
        command = text("SELECT * FROM guacamole_entity;")
        session = self.mock_session()
        backend = self.mock_backend(session=session)
        backend.execute_commands([command])
        session.execute.assert_called_once_with(command)

    def test_execute_commands_exception(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        command = text("SELECT * FROM guacamole_entity;")
        session = self.mock_session()
        session.execute.side_effect = OperationalError(
            statement="exception reason",
            params=None,
            orig=None,
        )
        backend = self.mock_backend(session=session)
        with pytest.raises(OperationalError, match="SQL: exception reason"):
            backend.execute_commands([command])
        assert "Unable to execute PostgreSQL commands." in caplog.text

    def test_query(self) -> None:
        session = self.mock_session()
        backend = self.mock_backend(session=session)
        backend.query(GuacamoleEntity)

        # Check method calls
        session.query.assert_called_once()
        session.filter.assert_not_called()
        session.delete.assert_not_called()
        session.__exit__.assert_called_once()

        # Check method arguments
        query_args = session.query.call_args.args
        assert len(query_args) == 1
        assert isinstance(query_args[0], type(GuacamoleEntity))

    def test_query_with_filter(self) -> None:
        session = self.mock_session()
        backend = self.mock_backend(session=session)
        backend.query(GuacamoleEntity, type=GuacamoleEntityType.USER)

        # Check method calls
        session.query.assert_called_once()
        session.filter_by.assert_called_once()
        session.__exit__.assert_called_once()

        # Check method arguments
        query_args = session.query.call_args.args
        assert len(query_args) == 1
        assert isinstance(query_args[0], type(GuacamoleEntity))
        filter_by_kwargs = session.filter_by.call_args.kwargs
        assert len(filter_by_kwargs) == 1
        assert "type" in filter_by_kwargs
        assert filter_by_kwargs["type"] == GuacamoleEntityType.USER


class TestPostgreSQLClient:
    """Test PostgreSQLClient."""

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
        caplog: pytest.LogCaptureFixture,
        ldap_model_groups_fixture: list[LDAPGroup],
        ldap_model_users_fixture: list[LDAPUser],
        postgresql_model_guacamoleentity_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
    ) -> None:
        # Create a mock backend
        mock_backend = MockPostgreSQLBackend(
            postgresql_model_guacamoleentity_fixture,
            postgresql_model_guacamoleusergroup_fixture,
        )

        # Capture logs at debug level and above
        caplog.set_level(logging.DEBUG)

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

            client = PostgreSQLClient(**self.client_kwargs)
            client.assign_users_to_groups(
                ldap_model_groups_fixture,
                ldap_model_users_fixture,
            )
            for output_line in (
                "Ensuring that 2 user(s) are correctly assigned among 3 group(s)",
                "Working on group 'defendants'",
                "Working on group 'everyone'",
                "Working on group 'plaintiffs'",
            ):
                assert output_line in caplog.text

    def test_assign_users_to_groups_missing_ldap_user(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_model_groups_fixture: list[LDAPGroup],
        ldap_model_users_fixture: list[LDAPUser],
        postgresql_model_guacamoleentity_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
    ) -> None:
        # Create a mock backend
        mock_backend = MockPostgreSQLBackend(
            postgresql_model_guacamoleentity_fixture,
            postgresql_model_guacamoleusergroup_fixture,
        )

        # Capture logs at debug level and above
        caplog.set_level(logging.DEBUG)

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

            client = PostgreSQLClient(**self.client_kwargs)
            client.assign_users_to_groups(
                ldap_model_groups_fixture,
                ldap_model_users_fixture[0:1],
            )
            for output_line in (
                "Ensuring that 1 user(s) are correctly assigned among 3 group(s)",
                "Could not find LDAP user with UID numerius.negidius",
                "... creating 2 user/group assignments",
            ):
                assert output_line in caplog.text

    def test_assign_users_to_groups_missing_user_entity(  # noqa: PLR0913
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_model_groups_fixture: list[LDAPGroup],
        ldap_model_users_fixture: list[LDAPUser],
        postgresql_model_guacamoleentity_user_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleentity_user_group_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
    ) -> None:
        # Create a mock backend
        mock_backend = MockPostgreSQLBackend(
            postgresql_model_guacamoleentity_user_fixture[1:],
            postgresql_model_guacamoleentity_user_group_fixture,
            postgresql_model_guacamoleusergroup_fixture,
        )

        # Capture logs at debug level and above
        caplog.set_level(logging.DEBUG)

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

            client = PostgreSQLClient(**self.client_kwargs)
            client.assign_users_to_groups(
                ldap_model_groups_fixture,
                ldap_model_users_fixture,
            )

            for output_line in (
                "Could not find entity ID for LDAP user 'aulus.agerius'",
            ):
                assert output_line in caplog.text

    def test_assign_users_to_groups_missing_usergroup(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_model_groups_fixture: list[LDAPGroup],
        ldap_model_users_fixture: list[LDAPUser],
        postgresql_model_guacamoleentity_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
    ) -> None:
        # Create a mock backend
        mock_backend = MockPostgreSQLBackend(
            postgresql_model_guacamoleentity_fixture,
            postgresql_model_guacamoleusergroup_fixture[1:],
        )

        # Capture logs at debug level and above
        caplog.set_level(logging.DEBUG)

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

            client = PostgreSQLClient(**self.client_kwargs)
            client.assign_users_to_groups(
                ldap_model_groups_fixture,
                ldap_model_users_fixture,
            )

            for output_line in (
                "Ensuring that 2 user(s) are correctly assigned among 3 group(s)",
                "Working on group 'defendants'",
                "Could not determine user_group_id for group 'defendants'.",
                "Group 'everyone' has entity_id: 2 and user_group_id: 12",
                "Group 'plaintiffs' has entity_id: 3 and user_group_id: 13",
            ):
                assert output_line in caplog.text

    def test_ensure_schema(self, capsys: pytest.CaptureFixture) -> None:
        # Create a mock backend
        mock_backend = MockPostgreSQLBackend()

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

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

    def test_ensure_schema_exception(self) -> None:
        # Create a mock backend
        def execute_commands_exception(
            commands: list[TextClause],  # noqa: ARG001
        ) -> None:
            raise OperationalError(statement="statement", params=None, orig=None)

        mock_backend = MockPostgreSQLBackend()
        mock_backend.execute_commands = execute_commands_exception  # type: ignore[method-assign]

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

            client = PostgreSQLClient(**self.client_kwargs)
            with pytest.raises(
                PostgreSQLError,
                match="Unable to ensure PostgreSQL schema.",
            ):
                client.ensure_schema(SchemaVersion.v1_5_5)

    def test_update(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_model_groups_fixture: list[LDAPGroup],
        ldap_model_users_fixture: list[LDAPUser],
    ) -> None:
        # Create a mock backend
        mock_backend = MockPostgreSQLBackend()

        # Capture logs at debug level and above
        caplog.set_level(logging.DEBUG)

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

            client = PostgreSQLClient(**self.client_kwargs)
            client.update(
                groups=ldap_model_groups_fixture,
                users=ldap_model_users_fixture,
            )
            for output_line in (
                "Ensuring that 3 group(s) are registered",
                "There are 0 group(s) currently registered",
                "... 3 group(s) will be added",
                "... 0 group(s) will be removed",
                "Ensuring that 2 user(s) are registered",
                "There are 0 user(s) currently registered",
                "... 2 user(s) will be added",
                "... 0 user(s) will be removed",
                "There are 0 user group entit(y|ies) currently registered",
                "... 3 user group entit(y|ies) will be added",
                "There are 3 valid user group entit(y|ies)",
                "There are 0 user entit(y|ies) currently registered",
                "... 2 user entit(y|ies) will be added",
                "There are 2 valid user entit(y|ies)",
                "Ensuring that 2 user(s) are correctly assigned among 3 group(s)",
                "Working on group 'defendants'",
                "Group 'defendants' has entity_id: None and user_group_id: None",
                "Group 'defendants' has 1 member(s).",
                " ... group member 'numerius.negidius@rome.la' has entity_id 'None'",
                "Working on group 'everyone'",
                "Group 'everyone' has entity_id: None and user_group_id: None",
                "Group 'everyone' has 2 member(s).",
                " ... group member 'aulus.agerius@rome.la' has entity_id 'None'",
                " ... group member 'numerius.negidius@rome.la' has entity_id 'None'",
                "Working on group 'plaintiffs'",
                "Group 'plaintiffs' has entity_id: None and user_group_id: None",
                "Group 'plaintiffs' has 1 member(s).",
                " ... group member 'aulus.agerius@rome.la' has entity_id 'None'",
                "... creating 4 user/group assignments.",
            ):
                assert output_line in caplog.text

    def test_update_group_entities(
        self,
        caplog: pytest.LogCaptureFixture,
        postgresql_model_guacamoleentity_user_group_fixture: list[GuacamoleEntity],
        postgresql_model_guacamoleusergroup_fixture: list[GuacamoleUserGroup],
    ) -> None:
        # Create a mock backend
        mock_backend = MockPostgreSQLBackend(
            postgresql_model_guacamoleentity_user_group_fixture,
            postgresql_model_guacamoleusergroup_fixture[0:1],
        )

        # Capture logs at debug level and above
        caplog.set_level(logging.DEBUG)

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

            client = PostgreSQLClient(**self.client_kwargs)
            client.update_group_entities()
            for output_line in (
                "There are 1 user group entit(y|ies) currently registered",
                "... 2 user group entit(y|ies) will be added",
                "There are 3 valid user group entit(y|ies)",
            ):
                assert output_line in caplog.text

    def test_update_groups(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_model_groups_fixture: list[LDAPGroup],
        postgresql_model_guacamoleentity_user_group_fixture: list[GuacamoleEntity],
    ) -> None:
        # Create a mock backend
        mock_backend = MockPostgreSQLBackend(
            postgresql_model_guacamoleentity_user_group_fixture[0:1],
            [
                GuacamoleEntity(
                    entity_id=99,
                    name="to-be-deleted",
                    type=GuacamoleEntityType.USER_GROUP,
                ),
            ],
        )

        # Capture logs at debug level and above
        caplog.set_level(logging.DEBUG)

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

            client = PostgreSQLClient(**self.client_kwargs)
            client.update_groups(ldap_model_groups_fixture)
            assert "Ensuring that 3 group(s) are registered" in caplog.text
            assert "There are 2 group(s) currently registered" in caplog.text
            assert "... 2 group(s) will be added" in caplog.text
            assert "... 1 group(s) will be removed" in caplog.text

    def test_update_user_entities(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_model_users_fixture: list[LDAPUser],
        postgresql_model_guacamoleuser_fixture: list[GuacamoleUser],
        postgresql_model_guacamoleentity_user_fixture: list[GuacamoleEntity],
    ) -> None:
        # Create a mock backend
        mock_backend = MockPostgreSQLBackend(
            postgresql_model_guacamoleentity_user_fixture,
            postgresql_model_guacamoleuser_fixture[0:1],
        )

        # Capture logs at debug level and above
        caplog.set_level(logging.DEBUG)

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

            client = PostgreSQLClient(**self.client_kwargs)
            client.update_user_entities(ldap_model_users_fixture)
            for output_line in (
                "There are 1 user entit(y|ies) currently registered",
                "... 1 user entit(y|ies) will be added",
                "There are 2 valid user entit(y|ies)",
            ):
                assert output_line in caplog.text

    def test_update_users(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_model_users_fixture: list[LDAPUser],
        postgresql_model_guacamoleentity_user_fixture: list[GuacamoleEntity],
    ) -> None:
        # Create a mock backend
        mock_backend = MockPostgreSQLBackend(
            postgresql_model_guacamoleentity_user_fixture[0:1],
            [
                GuacamoleEntity(
                    entity_id=99,
                    name="to-be-deleted",
                    type=GuacamoleEntityType.USER,
                ),
            ],
        )

        # Capture logs at debug level and above
        caplog.set_level(logging.DEBUG)

        # Patch PostgreSQLBackend
        with mock.patch(
            "guacamole_user_sync.postgresql.postgresql_client.PostgreSQLBackend",
        ) as mock_postgresql_backend:
            mock_postgresql_backend.return_value = mock_backend

            client = PostgreSQLClient(**self.client_kwargs)
            client.update_users(ldap_model_users_fixture)
            for output_line in (
                "Ensuring that 2 user(s) are registered",
                "There are 2 user(s) currently registered",
                "... 1 user(s) will be added",
                "... 1 user(s) will be removed",
            ):
                assert output_line in caplog.text
