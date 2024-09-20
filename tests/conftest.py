import pytest

from guacamole_user_sync.models import LDAPGroup, LDAPQuery, LDAPSearchResult, LDAPUser
from guacamole_user_sync.postgresql.orm import (
    GuacamoleEntity,
    GuacamoleUserGroup,
    guacamole_entity_type,
)


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
def ldap_response_groups_fixture() -> LDAPSearchResult:
    return [
        (
            0,
            (
                "CN=plaintiffs,OU=groups,DC=rome,DC=la",
                {
                    "cn": [b"plaintiffs"],
                    "memberOf": [],
                    "memberUid": [b"aulus.agerius"],
                },
            ),
        ),
        (
            1,
            (
                "CN=defendants,OU=groups,DC=rome,DC=la",
                {
                    "cn": [b"defendants"],
                    "memberOf": [],
                    "memberUid": [b"numerius.negidius"],
                },
            ),
        ),
        (
            2,
            (
                "CN=everyone,OU=groups,DC=rome,DC=la",
                {
                    "cn": [b"everyone"],
                    "memberOf": [],
                    "memberUid": [b"aulus.agerius", b"numerius.negidius"],
                },
            ),
        ),
    ]


@pytest.fixture
def ldap_response_users_fixture() -> LDAPSearchResult:
    return [
        (
            0,
            (
                "CN=aulus.agerius,OU=users,DC=rome,DC=la",
                {
                    "displayName": [b"Aulus Agerius"],
                    "memberOf": [b"CN=plaintiffs,OU=groups,DC=rome,DC=la"],
                    "uid": [b"aulus.agerius"],
                    "userName": [b"aulus.agerius@rome.la"],
                },
            ),
        ),
        (
            1,
            (
                "CN=numerius.negidius,OU=users,DC=rome,DC=la",
                {
                    "displayName": [b"Numerius Negidius"],
                    "memberOf": [b"CN=defendants,OU=groups,DC=rome,DC=la"],
                    "uid": [b"numerius.negidius"],
                    "userName": [b"numerius.negidius@rome.la"],
                },
            ),
        ),
    ]


@pytest.fixture
def postgresql_model_guacamoleentity_USER_GROUP_fixture() -> list[GuacamoleEntity]:
    return [
        GuacamoleEntity(
            entity_id=1, name="defendants", type=guacamole_entity_type.USER_GROUP
        ),
        GuacamoleEntity(
            entity_id=2, name="everyone", type=guacamole_entity_type.USER_GROUP
        ),
        GuacamoleEntity(
            entity_id=3, name="plaintiffs", type=guacamole_entity_type.USER_GROUP
        ),
    ]


@pytest.fixture
def postgresql_model_guacamoleentity_USER_fixture() -> list[GuacamoleEntity]:
    return [
        GuacamoleEntity(
            entity_id=4, name="aulus.agerius@rome.la", type=guacamole_entity_type.USER
        ),
        GuacamoleEntity(
            entity_id=5, name="numerius.negidius@rome.la", type=guacamole_entity_type.USER
        ),
    ]


@pytest.fixture
def postgresql_model_guacamoleentity_fixture(
    postgresql_model_guacamoleentity_USER_GROUP_fixture: list[GuacamoleEntity],
    postgresql_model_guacamoleentity_USER_fixture: list[GuacamoleEntity],
) -> list[GuacamoleEntity]:
    return (
        postgresql_model_guacamoleentity_USER_GROUP_fixture
        + postgresql_model_guacamoleentity_USER_fixture
    )


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
