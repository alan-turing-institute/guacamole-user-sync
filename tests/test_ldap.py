import logging
from typing import Any
from unittest import mock

import ldap
import pytest

from guacamole_user_sync.ldap import LDAPClient
from guacamole_user_sync.models import (
    LDAPError,
    LDAPGroup,
    LDAPQuery,
    LDAPSearchResult,
    LDAPUser,
)

from .mocks import (
    MockAsyncSearchListFullResults,
    MockAsyncSearchListPartialResults,
    MockLDAPObject,
)


class TestLDAPClient:
    """Test LDAPClient."""

    def test_constructor(self) -> None:
        client = LDAPClient(hostname="test-host")
        assert client.hostname == "test-host"

    def test_connect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def mock_initialize(uri: str) -> MockLDAPObject:
            return MockLDAPObject(uri)

        monkeypatch.setattr(ldap, "initialize", mock_initialize)

        client = LDAPClient(hostname="test-host")
        cnxn = client.connect()
        assert isinstance(cnxn, MockLDAPObject)
        assert cnxn.uri == "ldap://test-host"

    def test_connect_with_bind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def mock_initialize(uri: str) -> MockLDAPObject:
            return MockLDAPObject(uri)

        monkeypatch.setattr(ldap, "initialize", mock_initialize)

        client = LDAPClient(
            hostname="test-host",
            bind_dn="bind-dn",
            bind_password="bind_password",  # noqa: S106
        )
        cnxn = client.connect()
        assert isinstance(cnxn, MockLDAPObject)
        assert cnxn.bind_dn == "bind-dn"
        assert cnxn.bind_password == "bind_password"  # noqa: S105

    def test_connect_with_failed_bind(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def mock_initialize(uri: str) -> MockLDAPObject:
            return MockLDAPObject(uri)

        monkeypatch.setattr(ldap, "initialize", mock_initialize)

        client = LDAPClient(
            hostname="test-host",
            bind_dn="bind-dn",
            bind_password="incorrect-password",  # noqa: S106
        )
        with pytest.raises(LDAPError):
            client.connect()
        assert "Connection credentials were incorrect." in caplog.text

    def test_search_exception_server_down(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def mock_raise_server_down(*args: Any) -> None:  # noqa: ANN401
            raise ldap.SERVER_DOWN

        monkeypatch.setattr(
            ldap.asyncsearch.List, "startSearch", mock_raise_server_down
        )
        client = LDAPClient(hostname="test-host")
        with pytest.raises(LDAPError):
            client.search(query=LDAPQuery(base_dn="", filter="", id_attr=""))
        assert "Server could not be reached." in caplog.text

    def test_search_exception_sizelimit_exceeded(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def mock_raise_sizelimit_exceeded(*args: Any) -> None:  # noqa: ANN401
            raise ldap.SIZELIMIT_EXCEEDED

        monkeypatch.setattr(
            ldap.asyncsearch.List, "startSearch", mock_raise_sizelimit_exceeded
        )
        client = LDAPClient(hostname="test-host")
        with pytest.raises(LDAPError):
            client.search(query=LDAPQuery(base_dn="", filter="", id_attr=""))
        assert "Server-side size limit exceeded." in caplog.text

    def test_search_failure_partial(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_response_groups_fixture: LDAPSearchResult,
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.ldap.ldap_client.AsyncSearchList"
        ) as mock_async_search_list:
            mock_async_search_list.return_value = MockAsyncSearchListPartialResults(
                results=ldap_response_groups_fixture[0:1]
            )
            client = LDAPClient(hostname="test-host")
            client.search(query=LDAPQuery(base_dn="", filter="", id_attr=""))
        assert "Only partial results received." in caplog.text
        assert "Server returned 1 results." in caplog.text

    def test_search_no_results(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        def mock_raise_no_results(*args: Any) -> None:  # noqa: ANN401
            raise ldap.NO_SUCH_OBJECT

        monkeypatch.setattr(ldap.asyncsearch.List, "startSearch", mock_raise_no_results)
        client = LDAPClient(hostname="test-host")
        with pytest.raises(LDAPError):
            client.search(query=LDAPQuery(base_dn="", filter="", id_attr=""))
        assert "Server returned no results." in caplog.text

    def test_search_groups(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_query_groups_fixture: LDAPQuery,
        ldap_response_groups_fixture: LDAPSearchResult,
        ldap_model_groups_fixture: list[LDAPGroup],
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.ldap.ldap_client.AsyncSearchList"
        ) as mock_async_search_list:
            mock_async_search_list.return_value = MockAsyncSearchListFullResults(
                results=ldap_response_groups_fixture
            )
            client = LDAPClient(hostname="test-host")
            users = client.search_groups(query=ldap_query_groups_fixture)
            for user in ldap_model_groups_fixture:
                assert user in users
        assert "Server returned 3 results." in caplog.text
        assert "Loaded 3 LDAP groups" in caplog.text

    def test_search_users(
        self,
        caplog: pytest.LogCaptureFixture,
        ldap_query_users_fixture: LDAPQuery,
        ldap_response_users_fixture: LDAPSearchResult,
        ldap_model_users_fixture: list[LDAPUser],
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with mock.patch(
            "guacamole_user_sync.ldap.ldap_client.AsyncSearchList"
        ) as mock_async_search_list:
            mock_async_search_list.return_value = MockAsyncSearchListFullResults(
                results=ldap_response_users_fixture
            )
            client = LDAPClient(hostname="test-host")
            users = client.search_users(query=ldap_query_users_fixture)
            for user in ldap_model_users_fixture:
                assert user in users
        assert "Server returned 2 results." in caplog.text
        assert "Loaded 2 LDAP users" in caplog.text
