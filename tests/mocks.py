from typing import Any, Generic, TypeVar

from sqlalchemy.sql.expression import TextClause

from guacamole_user_sync.models import LDAPSearchResult


class MockLDAPObject:
    def __init__(self, uri: str) -> None:
        self.uri = uri


class MockAsyncSearchList:
    def __init__(
        self, partial: bool, results: LDAPSearchResult, *args: Any, **kwargs: Any
    ) -> None:
        self.allResults = results
        self.partial = partial

    def startSearch(self, *args: Any, **kwargs: Any) -> None:
        pass

    def processResults(self, *args: Any, **kwargs: Any) -> bool:
        return self.partial


class MockAsyncSearchListFullResults(MockAsyncSearchList):
    def __init__(self, results: LDAPSearchResult) -> None:
        super().__init__(results=results, partial=False)


class MockAsyncSearchListPartialResults(MockAsyncSearchList):
    def __init__(self, results: LDAPSearchResult) -> None:
        super().__init__(results=results, partial=True)


T = TypeVar("T")


class MockPostgreSQLBackend(Generic[T]):

    def __init__(
        self, *args: Any, **kwargs: Any
    ) -> None:
        self.contents: dict[T, list[T]] = {}

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

    def query(self, table: T, **filter_kwargs: Any) -> Any:
        results = [item for item in self.contents[table]]

        if "entity_id" in filter_kwargs:
            results = [item for item in results if item.entity_id == filter_kwargs["entity_id"]]

        if "name" in filter_kwargs:
            results = [item for item in results if item.name == filter_kwargs["name"]]

        if "type" in filter_kwargs:
            results = [item for item in results if item.type == filter_kwargs["type"]]

        return results
