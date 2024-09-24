from typing import Any, Generic, Type, TypeVar

import ldap
from sqlalchemy.sql.expression import TextClause

from guacamole_user_sync.models import LDAPSearchResult


class MockLDAPObject:
    """Mock LDAPObject."""

    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.bind_dn = ""
        self.bind_password = ""

    def simple_bind_s(self, bind_dn: str, bind_password: str) -> None:
        if bind_password == "incorrect-password":
            raise ldap.INVALID_CREDENTIALS
        self.bind_dn = bind_dn
        self.bind_password = bind_password


class MockAsyncSearchList:
    """Mock AsyncSearchList."""

    def __init__(
        self, partial: bool, results: LDAPSearchResult, *args: Any, **kwargs: Any
    ) -> None:
        self.allResults = results
        self.partial = partial

    def startSearch(self, *args: Any, **kwargs: Any) -> None:  # noqa: N802
        pass

    def processResults(self, *args: Any, **kwargs: Any) -> bool:  # noqa: N802
        return self.partial


class MockAsyncSearchListFullResults(MockAsyncSearchList):
    """Mock AsyncSearchList with full results."""

    def __init__(self, results: LDAPSearchResult) -> None:
        super().__init__(results=results, partial=False)


class MockAsyncSearchListPartialResults(MockAsyncSearchList):
    """Mock AsyncSearchList with partial results."""

    def __init__(self, results: LDAPSearchResult) -> None:
        super().__init__(results=results, partial=True)


T = TypeVar("T")


class MockPostgreSQLBackend(Generic[T]):
    """Mock PostgreSQLBackend."""

    def __init__(self, *data_lists: Any, **kwargs: Any) -> None:
        self.contents: dict[Type[T], list[T]] = {}
        for data_list in data_lists:
            self.add_all(data_list)

    def add_all(self, items: list[T]) -> None:
        cls = type(items[0])
        if cls not in self.contents:
            self.contents[cls] = []
        self.contents[cls] += items

    def delete(self, *args: Any, **kwargs: Any) -> None:
        pass

    def execute_commands(self, commands: list[TextClause]) -> None:
        for command in commands:
            print(f"Executing {command}")

    def query(self, table: Type[T], **filter_kwargs: Any) -> Any:
        if table not in self.contents:
            self.contents[table] = []
        results = [item for item in self.contents[table]]

        if "entity_id" in filter_kwargs:
            results = [
                item for item in results if item.entity_id == filter_kwargs["entity_id"]  # type: ignore
            ]

        if "name" in filter_kwargs:
            results = [item for item in results if item.name == filter_kwargs["name"]]  # type: ignore

        if "type" in filter_kwargs:
            results = [item for item in results if item.type == filter_kwargs["type"]]  # type: ignore

        return results
