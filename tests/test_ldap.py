from typing import Any
from unittest import mock

import ldap

from guacamole_user_sync.ldap import LDAPClient
from guacamole_user_sync.models import LDAPGroup, LDAPQuery, LDAPSearchResult, LDAPUser

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

    def test_search_groups(
        self,
        ldap_query_groups_fixture: LDAPQuery,
        ldap_response_groups_fixture: LDAPSearchResult,
        ldap_model_groups_fixture: list[LDAPGroup],
    ) -> None:
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

    def test_search_users(
        self,
        ldap_query_users_fixture: LDAPQuery,
        ldap_response_users_fixture: LDAPSearchResult,
        ldap_model_users_fixture: list[LDAPUser],
    ) -> None:
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
