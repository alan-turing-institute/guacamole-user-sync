import logging
from dataclasses import dataclass
from typing import Any, TypeVar

from sqlalchemy import URL, Engine, TextClause, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session

logger = logging.getLogger("guacamole_user_sync")


@dataclass
class PostgreSQLConnectionDetails:
    """Dataclass for holding PostgreSQL connection details."""

    database_name: str
    host_name: str
    port: int
    user_name: str
    user_password: str


T = TypeVar("T", bound=DeclarativeBase)


class PostgreSQLBackend:
    """Backend for connecting to a PostgreSQL database."""

    def __init__(
        self,
        *,
        connection_details: PostgreSQLConnectionDetails,
        session: Session | None = None,
    ) -> None:
        self.connection_details = connection_details
        self._engine: Engine | None = None
        self._session = session

    @property
    def engine(self) -> Engine:
        if not self._engine:
            url_object = URL.create(
                "postgresql+psycopg",
                username=self.connection_details.user_name,
                password=self.connection_details.user_password,
                host=self.connection_details.host_name,
                port=self.connection_details.port,
                database=self.connection_details.database_name,
            )
            self._engine = create_engine(url_object, echo=False)
        return self._engine

    def session(self) -> Session:
        if self._session:
            return self._session
        return Session(self.engine)

    def add_all(self, items: list[T]) -> None:
        with self.session() as session, session.begin():
            session.add_all(items)

    def delete(
        self,
        table: type[T],
        *filter_args: Any,  # noqa: ANN401
    ) -> None:
        with self.session() as session, session.begin():
            if filter_args:
                session.query(table).filter(*filter_args).delete()
            else:
                session.query(table).delete()

    def execute_commands(self, commands: list[TextClause]) -> None:
        try:
            with self.session() as session, session.begin():
                for command in commands:
                    session.execute(command)
        except SQLAlchemyError:
            logger.warning("Unable to execute PostgreSQL commands.")
            raise

    def query(
        self,
        table: type[T],
        **filter_kwargs: Any,  # noqa: ANN401
    ) -> list[T]:
        with self.session() as session, session.begin():
            if filter_kwargs:
                result = session.query(table).filter_by(**filter_kwargs)
            else:
                result = session.query(table)
        return list(result)
