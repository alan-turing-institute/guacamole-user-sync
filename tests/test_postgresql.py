from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.engine import URL, Engine  # type: ignore
from sqlalchemy.pool.impl import QueuePool

from guacamole_user_sync.postgresql import PostgreSQLClient


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
        assert client.database_name == "database_name"
        assert client.host_name == "host_name"
        assert client.port == 1234
        assert client.user_name == "user_name"
        assert client.user_password == "user_password"

    def test_engine(self) -> None:
        client = PostgreSQLClient(
            database_name="database_name",
            host_name="host_name",
            port=1234,
            user_name="user_name",
            user_password="user_password",
        )
        assert isinstance(client.engine, Engine)
        assert isinstance(client.engine.pool, QueuePool)
        assert isinstance(client.engine.dialect, PGDialect_psycopg)
        assert isinstance(client.engine.url, URL)
        assert client.engine.logging_name is None
        assert not client.engine.echo
        assert not client.engine.hide_parameters  # type: ignore
