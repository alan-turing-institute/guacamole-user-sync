import logging
from unittest import mock

import pytest
from ldap3 import Connection, Server
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPException,
    LDAPSessionTerminatedByServerError,
)

from guacamole_user_sync.ldap import LDAPClient
from guacamole_user_sync.models import (
    LDAPError,
    LDAPGroup,
    LDAPQuery,
    LDAPUser,
)

from .mocks import (
    MockLDAPAttribute,
    MockLDAPConnection,
    MockLDAPGroupEntry,
    MockLDAPServer,
    MockLDAPUserEntry,
)


class TestLDAPClient:
    """Test LDAPClient."""

    def test_constructor(self) -> None:
        client = LDAPClient("ldap://test-host")
        assert isinstance(client.server, Server)
        assert client.server.host == "test-host"
        assert client.group_member_attribute == "memberUid"

    def test_connect_invalid_server(self) -> None:
        client = LDAPClient("test-host")
        with pytest.raises(LDAPError, match="Server could not be reached."):
            client.connect()

    def test_connect(self) -> None:
        client = LDAPClient("test-host", auto_bind=False)
        cnxn = client.connect()
        assert isinstance(cnxn, Connection)

    def test_connect_with_bind(self) -> None:
        client = LDAPClient(
            "test-host",
            auto_bind=False,
            bind_dn="bind-dn",
            bind_password="bind_password",  # noqa: S106
        )
        cnxn = client.connect()
        assert isinstance(cnxn, Connection)
        assert cnxn.user == "bind-dn"
        assert cnxn.password == "bind_password"  # noqa: S105

    def test_connect_with_failed_bind(self, caplog: pytest.LogCaptureFixture) -> None:
        with mock.patch(
            "guacamole_user_sync.ldap.ldap_client.Connection",
            return_value=MockLDAPConnection(),
            side_effect=LDAPBindError(),
        ):
            client = LDAPClient(
                hostname="test-host",
                bind_dn="bind-dn",
                bind_password="incorrect-password",  # noqa: S106
            )
            with pytest.raises(LDAPError):
                client.connect()
            assert "Connection credentials were incorrect." in caplog.text

    def test_connect_unknown_exception(self) -> None:
        with mock.patch(
            "guacamole_user_sync.ldap.ldap_client.Connection",
            return_value=MockLDAPConnection(),
            side_effect=LDAPException(),
        ):
            client = LDAPClient(hostname="test-host", auto_bind=False)
            class_name = "<class 'ldap3.core.exceptions.LDAPException'>"
            with pytest.raises(
                LDAPError,
                match=f"Unexpected LDAP exception of type {class_name}",
            ):
                client.connect()

    @pytest.mark.parametrize(
        ("test_input", "expected"),
        [("test", ["test"]), (None, []), (["a", "b"], ["a", "b"])],
    )
    def test_as_list_valid(
        self,
        test_input: str | list[str] | None,
        expected: list[str],
    ) -> None:
        assert LDAPClient.as_list(test_input) == expected

    @pytest.mark.parametrize(("test_input", "expected"), [(42, "int"), (1.5, "float")])
    def test_as_list_invalid(self, test_input: float, expected: str) -> None:
        with pytest.raises(
            ValueError,
            match=f"Unexpected input {test_input} of type <class '{expected}'>",
        ):
            LDAPClient.as_list(test_input)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            ("aulus.agerius", "aulus.agerius"),
            (
                "uid=aulus.agerius,cn=users,cn=accounts,dc=rome,dc=la",
                "aulus.agerius",
            ),
            (
                "cn=Aulus Agerius,ou=users,dc=rome,dc=la",
                "cn=Aulus Agerius,ou=users,dc=rome,dc=la",
            ),
            ("=invalid", "=invalid"),
        ],
    )
    def test_member_uid(self, member: str, expected: str) -> None:
        assert LDAPClient.member_uid(member) == expected

    def test_search_session_terminated(self) -> None:
        with mock.patch(
            "guacamole_user_sync.ldap.ldap_client.Connection.search",
            return_value=[],
            side_effect=LDAPSessionTerminatedByServerError(),
        ):
            client = LDAPClient(hostname="test-host", auto_bind=False)
            with pytest.raises(
                LDAPError,
                match="Server terminated LDAP request.",
            ):
                client.search(query=LDAPQuery(base_dn="", filter="", id_attr=""))

    def test_search_unknown_exception(self) -> None:
        with mock.patch(
            "guacamole_user_sync.ldap.ldap_client.Connection.search",
            return_value=[],
            side_effect=LDAPException(),
        ):
            client = LDAPClient(hostname="test-host", auto_bind=False)
            class_name = "<class 'ldap3.core.exceptions.LDAPException'>"
            with pytest.raises(
                LDAPError,
                match=f"Unexpected LDAP exception of type {class_name}",
            ):
                client.search(query=LDAPQuery(base_dn="", filter="", id_attr=""))

    def test_search_no_results(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        caplog.set_level(logging.DEBUG)
        monkeypatch.setattr(
            LDAPClient,
            "connect",
            lambda _: MockLDAPConnection(server=MockLDAPServer([])),
        )
        client = LDAPClient(hostname="test-host", auto_bind=False)
        client.search(query=LDAPQuery(base_dn="", filter="", id_attr=""))
        assert "Server returned 0 results." in caplog.text

    def test_search_groups(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_query_groups_fixture: LDAPQuery,
        ldap_response_groups_fixture: list[MockLDAPGroupEntry],
        ldap_model_groups_fixture: list[LDAPGroup],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        caplog.set_level(logging.DEBUG)
        monkeypatch.setattr(
            LDAPClient,
            "connect",
            lambda _: MockLDAPConnection(
                server=MockLDAPServer(ldap_response_groups_fixture),
            ),
        )
        client = LDAPClient(hostname="test-host", auto_bind=False)
        groups = client.search_groups(query=ldap_query_groups_fixture)
        for group in ldap_model_groups_fixture:
            assert group in groups
        assert "base DN: OU=groups,DC=rome,DC=la" in caplog.text
        assert "Server returned 3 results." in caplog.text
        assert "Loaded 3 LDAP groups" in caplog.text

    def test_search_groups_custom_member_attribute(
        self,
        ldap_query_groups_fixture: LDAPQuery,
        ldap_response_groups_fixture: list[MockLDAPGroupEntry],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        entry = ldap_response_groups_fixture[0]
        entry.member = MockLDAPAttribute(
            ["uid=aulus.agerius,cn=users,cn=accounts,dc=rome,dc=la"],
        )
        monkeypatch.setattr(
            LDAPClient,
            "connect",
            lambda _: MockLDAPConnection(server=MockLDAPServer([entry])),
        )
        client = LDAPClient(
            hostname="test-host",
            auto_bind=False,
            group_member_attribute="member",
        )
        groups = client.search_groups(query=ldap_query_groups_fixture)
        assert groups[0].member_uid == ["aulus.agerius"]

    def test_search_groups_handles_missing_optional_attributes(
        self,
        ldap_query_groups_fixture: LDAPQuery,
        ldap_response_groups_fixture: list[MockLDAPGroupEntry],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        entry = ldap_response_groups_fixture[0]
        del entry.memberOf
        del entry.member
        monkeypatch.setattr(
            LDAPClient,
            "connect",
            lambda _: MockLDAPConnection(server=MockLDAPServer([entry])),
        )
        client = LDAPClient(
            hostname="test-host",
            auto_bind=False,
            group_member_attribute="member",
        )

        groups = client.search_groups(query=ldap_query_groups_fixture)

        assert groups[0].member_of == []
        assert groups[0].member_uid == []

    def test_search_users(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_query_users_fixture: LDAPQuery,
        ldap_response_users_fixture: list[MockLDAPUserEntry],
        ldap_model_users_fixture: list[LDAPUser],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        caplog.set_level(logging.DEBUG)
        monkeypatch.setattr(
            LDAPClient,
            "connect",
            lambda _: MockLDAPConnection(
                server=MockLDAPServer(ldap_response_users_fixture),
            ),
        )
        client = LDAPClient(hostname="test-host")
        users = client.search_users(query=ldap_query_users_fixture)
        for user in ldap_model_users_fixture:
            assert user in users
        assert "base DN: OU=users,DC=rome,DC=la" in caplog.text
        assert "Server returned 2 results." in caplog.text
        assert "Loaded 2 LDAP users" in caplog.text

    def test_search_users_handles_missing_optional_attributes(
        self,
        ldap_query_users_fixture: LDAPQuery,
        ldap_response_users_fixture: list[MockLDAPUserEntry],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        entry = ldap_response_users_fixture[0]
        del entry.displayName
        del entry.memberOf
        del entry.uid
        monkeypatch.setattr(
            LDAPClient,
            "connect",
            lambda _: MockLDAPConnection(server=MockLDAPServer([entry])),
        )
        client = LDAPClient(hostname="test-host", auto_bind=False)

        users = client.search_users(query=ldap_query_users_fixture)

        assert users[0].display_name == ""
        assert users[0].member_of == []
        assert users[0].uid == ""
