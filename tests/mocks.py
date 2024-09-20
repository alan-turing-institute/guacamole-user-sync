from typing import Any, Generic, TypeVar

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
        self, query_results: dict[T, list[list[T]]], *args: Any, **kwargs: Any
    ) -> None:
        self.query_results = query_results

    def add_all(self, *args: Any, **kwargs: Any) -> None:
        pass

    def delete(self, *args: Any, **kwargs: Any) -> None:
        pass

    def execute_commands(self, *args: Any, **kwargs: Any) -> None:
        pass

    def query(self, table: T, **filter_kwargs: Any) -> Any:
        return self.query_results[table].pop()
