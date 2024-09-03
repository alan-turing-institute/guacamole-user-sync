import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import OperationalError

from .schema import GuacamoleSchema, SchemaVersion

logger = logging.getLogger("guacamole_user_sync")

LDAPSearchResult = list[tuple[int, tuple[str, dict[str, list[bytes]]]]]


class PostgresqlClient:
    def __init__(
        self,
        *,
        database_name: str,
        host_name: str,
        port: int,
        user_name: str,
        user_password: str,
    ):
        self.database_name = database_name
        self.host_name = host_name
        self.port = port
        self.user_name = user_name
        self.user_password = user_password
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        if not self._engine:
            url_object = URL.create(
                "postgresql+psycopg",
                username=self.user_name,
                password=self.user_password,
                host=self.host_name,
                port=self.port,
                database=self.database_name,
            )
            self._engine = create_engine(url_object, echo=False)
        return self._engine

    def ensure_schema(self, schema_version: SchemaVersion) -> None:
        try:
            with self.engine.begin() as cnxn:
                for command in GuacamoleSchema.commands(schema_version):
                    cnxn.execute(command)
        except OperationalError:
            logger.warning("Unable to connect to the PostgreSQL server.")
            return None
