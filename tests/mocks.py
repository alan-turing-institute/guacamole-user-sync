from typing import Any

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


# class MockSession:
#     def __init__(self, *args: Any, **kwargs: Any) -> None:
#         pass

#     def startSearch(self, *args: Any, **kwargs: Any) -> None:
#         pass

#     def processResults(self, *args: Any, **kwargs: Any) -> bool:
#         return self.partial
