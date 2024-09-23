import logging
from typing import Any, TypeVar

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine  # type:ignore
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import TextClause

logger = logging.getLogger("guacamole_user_sync")

T = TypeVar("T")


class PostgreSQLBackend:
    def __init__(
        self,
        *,
        database_name: str,
        host_name: str,
        port: int,
        user_name: str,
        user_password: str,
        session: Session | None = None,
    ):
        self.database_name = database_name
        self.host_name = host_name
        self.port = port
        self.user_name = user_name
        self.user_password = user_password
        self._engine: Engine | None = None
        self._session = session

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

    def session(self) -> Session:
        if self._session:
            return self._session
        return Session(self.engine)

    def add_all(self, items: list[T]) -> None:
        with self.session() as session:  # type:ignore
            with session.begin():
                session.add_all(items)

    def delete(self, table: T, *filter_args: Any) -> None:
        with self.session() as session:  # type:ignore
            with session.begin():
                if filter_args:
                    session.query(table).filter(*filter_args).delete()
                else:
                    session.query(table).delete()

    def execute_commands(self, commands: list[TextClause]) -> None:
        with self.session() as session:  # type:ignore
            with session.begin():
                for command in commands:
                    session.execute(command)

    def query(self, table: T, **filter_kwargs: Any) -> list[T]:
        with self.session() as session:  # type:ignore
            with session.begin():
                if filter_kwargs:
                    result = session.query(table).filter_by(**filter_kwargs)
                else:
                    result = session.query(table)
        return [item for item in result]
