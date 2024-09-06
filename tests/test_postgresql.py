from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.engine import URL, Engine  # type: ignore
from sqlalchemy.pool.impl import QueuePool

from guacamole_user_sync.postgresql import PostgreSQLBackend, PostgreSQLClient


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
    client = PostgreSQLClient(
        database_name="database_name",
        host_name="host_name",
        port=1234,
        user_name="user_name",
        user_password="user_password",
    )

    def test_constructor(self) -> None:
        assert isinstance(self.client, PostgreSQLClient)
        assert isinstance(self.client.backend, PostgreSQLBackend)
