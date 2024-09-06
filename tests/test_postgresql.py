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
