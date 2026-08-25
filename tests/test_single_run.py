from unittest import mock

import synchronise as synchronise_module


def _main_kwargs() -> dict[str, object]:
    return {
        "guacamole_group_permissions": None,
        "ldap_bind_dn": None,
        "ldap_bind_password": None,
        "ldap_group_base_dn": "ou=groups,dc=example,dc=com",
        "ldap_group_filter": "(objectClass=*)",
        "ldap_group_name_attr": "cn",
        "ldap_host": "ldap.example.com",
        "ldap_port": 389,
        "ldap_user_base_dn": "ou=users,dc=example,dc=com",
        "ldap_user_filter": "(objectClass=*)",
        "ldap_user_name_attr": "uid",
        "postgresql_database_name": "guacamole",
        "postgresql_host_name": "postgres.example.com",
        "postgresql_password": "test-password",
        "postgresql_port": 5432,
        "postgresql_user_name": "guacamole",
        "repeat_interval": 300,
        "ldap_group_member_attr": "member",
        "single_run_mode": True,
    }


def test_main_single_run_success() -> None:
    with (
        mock.patch.object(synchronise_module, "LDAPClient") as ldap_client_cls,
        mock.patch.object(synchronise_module, "PostgreSQLClient"),
        mock.patch.object(
            synchronise_module,
            "synchronise",
            return_value=True,
        ) as synchronise_mock,
        mock.patch.object(synchronise_module.time, "sleep") as sleep_mock,
    ):
        result = synchronise_module.main(**_main_kwargs())  # type: ignore[arg-type]

    assert result == 0
    ldap_client_cls.assert_called_once_with(
        "ldap.example.com:389",
        bind_dn=None,
        bind_password=None,
        group_member_attribute="member",
    )
    synchronise_mock.assert_called_once_with(
        guacamole_group_permissions=None,
        ldap_client=mock.ANY,
        ldap_group_query=mock.ANY,
        ldap_user_query=mock.ANY,
        postgresql_client=mock.ANY,
    )
    sleep_mock.assert_not_called()


def test_main_single_run_failure_returns_nonzero() -> None:
    with (
        mock.patch.object(synchronise_module, "LDAPClient"),
        mock.patch.object(synchronise_module, "PostgreSQLClient"),
        mock.patch.object(synchronise_module, "synchronise", return_value=False),
        mock.patch.object(synchronise_module.time, "sleep") as sleep_mock,
    ):
        result = synchronise_module.main(**_main_kwargs())  # type: ignore[arg-type]

    assert result == 1
    sleep_mock.assert_not_called()


def test_synchronise_reports_success() -> None:
    ldap_client = mock.MagicMock()
    ldap_client.search_groups.return_value = []
    ldap_client.search_users.return_value = []
    postgresql_client = mock.MagicMock()

    result = synchronise_module.synchronise(
        guacamole_group_permissions=None,
        ldap_client=ldap_client,
        ldap_group_query=mock.MagicMock(),
        ldap_user_query=mock.MagicMock(),
        postgresql_client=postgresql_client,
    )

    assert result is True
    postgresql_client.update.assert_called_once_with(
        groups=[],
        users=[],
        group_permissions=None,
    )


def test_synchronise_reports_ldap_failure() -> None:
    ldap_client = mock.MagicMock()
    ldap_client.search_groups.side_effect = synchronise_module.LDAPError("LDAP failed")

    result = synchronise_module.synchronise(
        guacamole_group_permissions=None,
        ldap_client=ldap_client,
        ldap_group_query=mock.MagicMock(),
        ldap_user_query=mock.MagicMock(),
        postgresql_client=mock.MagicMock(),
    )

    assert result is False


def test_synchronise_reports_postgresql_failure() -> None:
    ldap_client = mock.MagicMock()
    ldap_client.search_groups.return_value = []
    ldap_client.search_users.return_value = []
    postgresql_client = mock.MagicMock()
    postgresql_client.ensure_schema.side_effect = synchronise_module.PostgreSQLError(
        "PostgreSQL failed"
    )

    result = synchronise_module.synchronise(
        guacamole_group_permissions=None,
        ldap_client=ldap_client,
        ldap_group_query=mock.MagicMock(),
        ldap_user_query=mock.MagicMock(),
        postgresql_client=postgresql_client,
    )

    assert result is False
