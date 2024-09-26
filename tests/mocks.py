from typing import Any

import ldap
from sqlalchemy.sql.expression import TextClause

from guacamole_user_sync.models import LDAPSearchResult
from guacamole_user_sync.postgresql.orm import GuacamoleBase


class MockLDAPObject:
    """Mock LDAPObject."""

    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.bind_dn = ""
        self.bind_password = ""

    def simple_bind_s(self, bind_dn: str, bind_password: str) -> None:
        if bind_password == "incorrect-password":  # noqa: S105
            raise ldap.INVALID_CREDENTIALS
        self.bind_dn = bind_dn
        self.bind_password = bind_password


class MockAsyncSearchList:
    """Mock AsyncSearchList."""

    def __init__(
        self,
        partial: bool,  # noqa: FBT001
        results: LDAPSearchResult,
        *args: Any,  # noqa: ANN401, ARG002
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> None:
        self.allResults = results
        self.partial = partial

    def startSearch(  # noqa: N802
        self,
        *args: Any,  #  noqa: ANN401, ARG002
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> None:
        pass

    def processResults(  # noqa: N802
        self,
        *args: Any,  # noqa: ANN401, ARG002
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> bool:
        return self.partial


class MockAsyncSearchListFullResults(MockAsyncSearchList):
    """Mock AsyncSearchList with full results."""

    def __init__(self, results: LDAPSearchResult) -> None:
        super().__init__(results=results, partial=False)


class MockAsyncSearchListPartialResults(MockAsyncSearchList):
    """Mock AsyncSearchList with partial results."""

    def __init__(self, results: LDAPSearchResult) -> None:
        super().__init__(results=results, partial=True)


class MockPostgreSQLBackend:
    """Mock PostgreSQLBackend."""

    def __init__(self, *data_lists: Any, **kwargs: Any) -> None:  # noqa: ANN401, ARG002
        self.contents: dict[type[GuacamoleBase], list[GuacamoleBase]] = {}
        for data_list in data_lists:
            self.add_all(data_list)

    def add_all(self, items: list[GuacamoleBase]) -> None:
        cls = type(items[0])
        if cls not in self.contents:
            self.contents[cls] = []
        self.contents[cls] += items

    def delete(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401, ARG001
        pass

    def execute_commands(self, commands: list[TextClause]) -> None:
        for command in commands:
            print(f"Executing {command}")  # noqa: T201

    def query(
        self,
        table: type[GuacamoleBase],
        **filter_kwargs: Any,  # noqa: ANN401
    ) -> list[GuacamoleBase]:
        if table not in self.contents:
            self.contents[table] = []
        results = list(self.contents[table])

        if "entity_id" in filter_kwargs:
            results = [
                item for item in results if item.entity_id == filter_kwargs["entity_id"]
            ]

        if "name" in filter_kwargs:
            results = [item for item in results if item.name == filter_kwargs["name"]]

        if "type" in filter_kwargs:
            results = [item for item in results if item.type == filter_kwargs["type"]]

        return results
