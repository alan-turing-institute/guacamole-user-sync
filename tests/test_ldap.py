import logging
from typing import Any
from unittest import mock

import ldap
import pytest

from guacamole_user_sync.ldap import LDAPClient
from guacamole_user_sync.models import (
    LDAPException,
    LDAPGroup,
    LDAPQuery,
    LDAPSearchResult,
    LDAPUser,
)

from .mocks import MockAsyncSearchListFullResults, MockLDAPObject


class TestLDAPClient:
    def test_constructor(self) -> None:
        client = LDAPClient(hostname="test-host")
        assert client.hostname == "test-host"

    def test_host(self, monkeypatch: Any) -> None:
        def mock_initialize(uri: str) -> MockLDAPObject:
            return MockLDAPObject(uri)

        monkeypatch.setattr(ldap, "initialize", mock_initialize)

        client = LDAPClient(hostname="test-host")
        assert isinstance(client.host, MockLDAPObject)
        assert client.host.uri == "ldap://test-host"

    def test_search_exception_server_down(self, monkeypatch: Any, caplog: Any) -> None:
        def mock_raise_server_down(*args: Any) -> None:
            raise ldap.SERVER_DOWN

        monkeypatch.setattr(
            ldap.asyncsearch.List, "startSearch", mock_raise_server_down
        )
        client = LDAPClient(hostname="test-host")
        with pytest.raises(LDAPException):
            client.search(query=LDAPQuery(base_dn="", filter="", id_attr=""))
        assert "Server could not be reached." in caplog.text

    def test_search_exception_sizelimit_exceeded(
        self, monkeypatch: Any, caplog: Any
    ) -> None:
        def mock_raise_sizelimit_exceeded(*args: Any) -> None:
            raise ldap.SIZELIMIT_EXCEEDED

        monkeypatch.setattr(
            ldap.asyncsearch.List, "startSearch", mock_raise_sizelimit_exceeded
        )
        client = LDAPClient(hostname="test-host")
        with pytest.raises(LDAPException):
            client.search(query=LDAPQuery(base_dn="", filter="", id_attr=""))
        assert "Server-side size limit exceeded." in caplog.text

    def test_search_groups(
        self,
        caplog: Any,
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
        assert "Loaded 3 LDAP groups" in caplog.text

    def test_search_users(
        self,
        caplog: Any,
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
        assert "Loaded 2 LDAP users" in caplog.text
