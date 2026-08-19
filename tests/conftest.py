from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry

from guacamole_user_sync.models import LDAPGroup, LDAPQuery, LDAPUser
from guacamole_user_sync.postgresql import (
    PostgreSQLBackend,
    PostgreSQLConnectionDetails,
)
from guacamole_user_sync.postgresql.orm import (
    GuacamoleEntity,
    GuacamoleEntityType,
    GuacamoleUser,
    GuacamoleUserGroup,
)
from guacamole_user_sync.postgresql.sql import GuacamoleSchema, SchemaVersion

from .mocks import MockLDAPGroupEntry, MockLDAPUserEntry


@pytest.fixture
def ldap_model_groups_fixture() -> list[LDAPGroup]:
    return [
        LDAPGroup(
            member_of=[],
            member_uid=["numerius.negidius"],
            name="defendants",
        ),
        LDAPGroup(
            member_of=[],
            member_uid=["aulus.agerius", "numerius.negidius"],
            name="everyone",
        ),
        LDAPGroup(
            member_of=[],
            member_uid=["aulus.agerius"],
            name="plaintiffs",
        ),
    ]


@pytest.fixture
def ldap_model_users_fixture() -> list[LDAPUser]:
    return [
        LDAPUser(
            display_name="Aulus Agerius",
            member_of=["CN=plaintiffs,OU=groups,DC=rome,DC=la"],
            name="aulus.agerius@rome.la",
            uid="aulus.agerius",
        ),
        LDAPUser(
            display_name="Numerius Negidius",
            member_of=["CN=defendants,OU=groups,DC=rome,DC=la"],
            name="numerius.negidius@rome.la",
            uid="numerius.negidius",
        ),
    ]


@pytest.fixture
def ldap_query_groups_fixture() -> LDAPQuery:
    return LDAPQuery(
        base_dn="OU=groups,DC=rome,DC=la",
        filter="(objectClass=posixGroup)",
        id_attr="cn",
    )


@pytest.fixture
def ldap_query_users_fixture() -> LDAPQuery:
    return LDAPQuery(
        base_dn="OU=users,DC=rome,DC=la",
        filter="(objectClass=posixAccount)",
        id_attr="userName",
    )


@pytest.fixture
def ldap_response_groups_fixture() -> list[MockLDAPGroupEntry]:
    return [
        MockLDAPGroupEntry(
            dn="CN=plaintiffs,OU=groups,DC=rome,DC=la",
            cn="plaintiffs",
            memberOf=[],
            memberUid=["aulus.agerius"],
        ),
        MockLDAPGroupEntry(
            dn="CN=defendants,OU=groups,DC=rome,DC=la",
            cn="defendants",
            memberOf=[],
            memberUid=["numerius.negidius"],
        ),
        MockLDAPGroupEntry(
            dn="CN=everyone,OU=groups,DC=rome,DC=la",
            cn="everyone",
            memberOf=[],
            memberUid=["aulus.agerius", "numerius.negidius"],
        ),
    ]


@pytest.fixture
def ldap_response_users_fixture() -> list[MockLDAPUserEntry]:
    return [
        MockLDAPUserEntry(
            dn="CN=aulus.agerius,OU=users,DC=rome,DC=la",
            displayName="Aulus Agerius",
            memberOf=["CN=plaintiffs,OU=groups,DC=rome,DC=la"],
            uid="aulus.agerius",
            userName="aulus.agerius@rome.la",
        ),
        MockLDAPUserEntry(
            dn="CN=numerius.negidius,OU=users,DC=rome,DC=la",
            displayName="Numerius Negidius",
            memberOf=["CN=defendants,OU=groups,DC=rome,DC=la"],
            uid="numerius.negidius",
            userName="numerius.negidius@rome.la",
        ),
    ]


@pytest.fixture
def postgresql_model_guacamoleentity_user_group_fixture() -> list[GuacamoleEntity]:
    return [
        GuacamoleEntity(
            entity_id=1,
            name="defendants",
            type=GuacamoleEntityType.USER_GROUP,
        ),
        GuacamoleEntity(
            entity_id=2,
            name="everyone",
            type=GuacamoleEntityType.USER_GROUP,
        ),
        GuacamoleEntity(
            entity_id=3,
            name="plaintiffs",
            type=GuacamoleEntityType.USER_GROUP,
        ),
    ]


@pytest.fixture
def postgresql_model_guacamoleentity_user_fixture() -> list[GuacamoleEntity]:
    return [
        GuacamoleEntity(
            entity_id=4,
            name="aulus.agerius@rome.la",
            type=GuacamoleEntityType.USER,
        ),
        GuacamoleEntity(
            entity_id=5,
            name="numerius.negidius@rome.la",
            type=GuacamoleEntityType.USER,
        ),
    ]


@pytest.fixture
def postgresql_model_guacamoleentity_fixture(
    postgresql_model_guacamoleentity_user_group_fixture: list[GuacamoleEntity],
    postgresql_model_guacamoleentity_user_fixture: list[GuacamoleEntity],
) -> list[GuacamoleEntity]:
    return (
        postgresql_model_guacamoleentity_user_group_fixture
        + postgresql_model_guacamoleentity_user_fixture
    )


@pytest.fixture
def postgresql_model_guacamoleuser_fixture() -> list[GuacamoleUser]:
    return [
        GuacamoleUser(
            user_id=1,
            entity_id=4,
            full_name="Aulus Agerius",
            password_hash=b"PASSWORD_HASH",
            password_salt=b"PASSWORD_SALT",
            password_date=datetime(1, 1, 1, tzinfo=UTC),
        ),
        GuacamoleUser(
            user_id=2,
            entity_id=5,
            full_name="Numerius Negidius",
            password_hash=b"PASSWORD_HASH",
            password_salt=b"PASSWORD_SALT",
            password_date=datetime(1, 1, 1, tzinfo=UTC),
        ),
    ]


@pytest.fixture
def postgresql_model_guacamoleusergroup_fixture() -> list[GuacamoleUserGroup]:
    return [
        GuacamoleUserGroup(
            entity_id=1,
            user_group_id=11,
        ),
        GuacamoleUserGroup(
            entity_id=2,
            user_group_id=12,
        ),
        GuacamoleUserGroup(
            entity_id=3,
            user_group_id=13,
        ),
    ]


def _enable_sqlite_foreign_keys(
    dbapi_connection: DBAPIConnection,
    _connection_record: ConnectionPoolEntry,
) -> None:
    """Enable SQLite's foreign-key enforcement pragma on a new connection.

    See https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def postgresql_sqlite_backend_fixture() -> Generator[PostgreSQLBackend, None, None]:
    """Build a PostgreSQLBackend against a fresh in-memory copy of the real schema.

    A new engine is created per test (the default fixture scope), so tests
    never share database state and can run in any order or in parallel.
    """
    engine = create_engine("sqlite+pysqlite:///:memory:")
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)

    # SQLite has no CREATE TYPE/enum support, so skip the 5 Postgres-only
    # `DO $$ ... $$` enum-creation blocks; every other statement in the real
    # schema file runs unmodified.
    schema_commands = [
        command
        for command in GuacamoleSchema.commands(SchemaVersion.v1_5_5)
        if "DO $$" not in command.text
    ]
    with engine.begin() as connection:
        for command in schema_commands:
            connection.execute(command)

    # A pre-built session is returned as-is by PostgreSQLBackend.session(),
    # so expire_on_commit must be set here rather than per-call; see
    # https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.expire_on_commit.
    with Session(engine, expire_on_commit=False) as session:
        yield PostgreSQLBackend(
            connection_details=PostgreSQLConnectionDetails(
                database_name="database_name",
                host_name="host_name",
                port=1234,
                user_name="user_name",
                user_password="user_password",  # noqa: S106
            ),
            session=session,
        )

    engine.dispose()
