from typing import Any

from ldap3.core.exceptions import LDAPBindError
from sqlalchemy import TextClause

from guacamole_user_sync.postgresql.orm import GuacamoleBase


class MockLDAPAttribute:
    """Mock LDAP value."""

    def __init__(self, value: str | float | list[str]) -> None:
        self.value = value


class MockLDAPGroupEntry:
    """Mock LDAP group entry."""

    def __init__(
        self,
        dn: str,
        cn: str,
        memberOf: list[str],  # noqa: N803
        memberUid: list[str],  # noqa: N803
    ) -> None:
        self.dn = MockLDAPAttribute(dn)
        self.cn = MockLDAPAttribute(cn)
        self.memberOf = MockLDAPAttribute(memberOf)
        self.memberUid = MockLDAPAttribute(memberUid)


class MockLDAPUserEntry:
    """Mock LDAP user entry."""

    def __init__(
        self,
        dn: str,
        displayName: str,  # noqa: N803
        memberOf: list[str],  # noqa: N803
        uid: str,
        userName: str,  # noqa: N803
    ) -> None:
        self.dn = MockLDAPAttribute(dn)
        self.displayName = MockLDAPAttribute(displayName)
        self.memberOf = MockLDAPAttribute(memberOf)
        self.uid = MockLDAPAttribute(uid)
        self.userName = MockLDAPAttribute(userName)


class MockLDAPServer:
    """Mock LDAP server."""

    def __init__(
        self,
        entries: list[MockLDAPGroupEntry] | list[MockLDAPUserEntry],
    ) -> None:
        self.entries = entries


class MockLDAPConnection:
    """Mock LDAP connection."""

    def __init__(
        self,
        server: MockLDAPServer | None = None,
        user: str | None = None,
        password: str | None = None,
        *,
        auto_bind: bool = False,
    ) -> None:
        self.auto_bind = auto_bind
        self.password = password
        if password == "incorrect-password":  # noqa: S105
            raise LDAPBindError
        self.server = server
        self.user = user

    def search(
        self,
        base_dn: str,  # noqa: ARG002
        ldap_filter: str,  # noqa: ARG002
        attributes: str,  # noqa: ARG002
    ) -> None:
        if self.server:
            self.entries = self.server.entries


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

    def delete(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
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
