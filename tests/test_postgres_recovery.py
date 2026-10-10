"""Regression tests for transient PostgreSQL connection failures."""

import logging
from typing import cast
from unittest import mock

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

import synchronise
from guacamole_user_sync.ldap import LDAPClient
from guacamole_user_sync.models import LDAPQuery
from guacamole_user_sync.postgresql import (
    PostgreSQLBackend,
    PostgreSQLClient,
    PostgreSQLConnectionDetails,
)


def test_engine_checks_pooled_connections_and_times_out_on_connect() -> None:
    backend = PostgreSQLBackend(
        connection_details=PostgreSQLConnectionDetails(
            database_name="guacamole",
            host_name="example.test",
            port=5432,
            user_name="user",
            user_password="password",  # noqa: S106
        ),
    )
    with mock.patch(
        "guacamole_user_sync.postgresql.postgresql_backend.create_engine",
        return_value=mock.Mock(spec=Engine),
    ) as create_engine:
        engine = backend.engine
        assert engine is backend.engine

    create_engine.assert_called_once()
    assert create_engine.call_args.kwargs == {
        "echo": False,
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 30},
    }


def test_sqlalchemy_timeout_does_not_prevent_next_sync(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    ldap = mock.Mock(spec=LDAPClient)
    ldap.search_groups.return_value = []
    ldap.search_users.return_value = []
    postgres = mock.Mock(spec=PostgreSQLClient)
    postgres.ensure_schema.side_effect = [
        OperationalError("SELECT 1", None, TimeoutError("Connection timed out")),
        None,
    ]
    query = LDAPQuery(
        base_dn="dc=example,dc=test",
        filter="(objectClass=*)",
        id_attr="cn",
    )

    for _ in range(2):
        synchronise.synchronise(
            guacamole_group_permissions=None,
            ldap_client=cast(LDAPClient, ldap),
            ldap_group_query=query,
            ldap_user_query=query,
            postgresql_client=cast(PostgreSQLClient, postgres),
        )

    assert postgres.ensure_schema.call_count == 2  # noqa: PLR2004
    postgres.update.assert_called_once_with(
        groups=[],
        users=[],
        group_permissions=None,
    )
    assert "PostgreSQL update failed; retrying at the next interval." in caplog.text
