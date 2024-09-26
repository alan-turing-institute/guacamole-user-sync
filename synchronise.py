#! /usr/bin/env python3
import logging
import os
import time

from guacamole_user_sync.ldap import LDAPClient
from guacamole_user_sync.models import LDAPError, LDAPQuery, PostgreSQLError
from guacamole_user_sync.postgresql import PostgreSQLClient, SchemaVersion


def main(
    ldap_bind_dn: str | None,
    ldap_bind_password: str | None,
    ldap_group_base_dn: str,
    ldap_group_filter: str,
    ldap_group_name_attr: str,
    ldap_host: str,
    ldap_port: int,
    ldap_user_base_dn: str,
    ldap_user_filter: str,
    ldap_user_name_attr: str,
    postgresql_database_name: str,
    postgresql_host_name: str,
    postgresql_password: str,
    postgresql_port: int,
    postgresql_user_name: str,
    repeat_interval: int,
) -> None:
    # Initialise LDAP resources
    ldap_client = LDAPClient(
        f"{ldap_host}:{ldap_port}",
        bind_dn=ldap_bind_dn,
        bind_password=ldap_bind_password,
    )
    ldap_group_query = LDAPQuery(
        base_dn=ldap_group_base_dn,
        filter=ldap_group_filter,
        id_attr=ldap_group_name_attr,
    )
    ldap_user_query = LDAPQuery(
        base_dn=ldap_user_base_dn,
        filter=ldap_user_filter,
        id_attr=ldap_user_name_attr,
    )
    postgresql_client = PostgreSQLClient(
        database_name=postgresql_database_name,
        host_name=postgresql_host_name,
        port=postgresql_port,
        user_name=postgresql_user_name,
        user_password=postgresql_password,
    )

    # Loop until terminated
    while True:
        # Run synchronisation step
        synchronise(
            ldap_client=ldap_client,
            ldap_group_query=ldap_group_query,
            ldap_user_query=ldap_user_query,
            postgresql_client=postgresql_client,
        )

        # Wait before repeating
        logger.info("Waiting %s seconds.", repeat_interval)
        time.sleep(repeat_interval)


def synchronise(
    *,
    ldap_client: LDAPClient,
    ldap_group_query: LDAPQuery,
    ldap_user_query: LDAPQuery,
    postgresql_client: PostgreSQLClient,
) -> None:
    logger.info("Starting synchronisation.")
    try:
        ldap_groups = ldap_client.search_groups(ldap_group_query)
        ldap_users = ldap_client.search_users(ldap_user_query)
    except LDAPError:
        logger.warning("LDAP server query failed")
        return

    try:
        postgresql_client.ensure_schema(SchemaVersion.v1_5_5)
        postgresql_client.update(groups=ldap_groups, users=ldap_users)
    except PostgreSQLError:
        logger.warning("PostgreSQL update failed")
        return


if __name__ == "__main__":
    if not (ldap_host := os.getenv("LDAP_HOST", None)):
        msg = "LDAP_HOST is not defined"
        raise ValueError(msg)
    if not (ldap_group_base_dn := os.getenv("LDAP_GROUP_BASE_DN", None)):
        msg = "LDAP_GROUP_BASE_DN is not defined"
        raise ValueError(msg)
    if not (ldap_group_filter := os.getenv("LDAP_GROUP_FILTER", None)):
        msg = "LDAP_GROUP_FILTER is not defined"
        raise ValueError(msg)

    if not (ldap_user_base_dn := os.getenv("LDAP_USER_BASE_DN", None)):
        msg = "LDAP_USER_BASE_DN is not defined"
        raise ValueError(msg)
    if not (ldap_user_filter := os.getenv("LDAP_USER_FILTER", None)):
        msg = "LDAP_USER_FILTER is not defined"
        raise ValueError(msg)

    if not (postgresql_host_name := os.getenv("POSTGRESQL_HOST", None)):
        msg = "POSTGRESQL_HOST is not defined"
        raise ValueError(msg)
    if not (postgresql_password := os.getenv("POSTGRESQL_PASSWORD", None)):
        msg = "POSTGRESQL_PASSWORD is not defined"
        raise ValueError(msg)
    if not (postgresql_user_name := os.getenv("POSTGRESQL_USERNAME", None)):
        msg = "POSTGRESQL_USERNAME is not defined"
        raise ValueError(msg)

    logging.basicConfig(
        level=(
            logging.DEBUG
            if os.getenv("DEBUG", "False").lower() == "true"
            else logging.INFO
        ),
        format=r"%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt=r"%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("guacamole_user_sync")

    main(
        ldap_bind_dn=os.getenv("LDAP_BIND_DN", None),
        ldap_bind_password=os.getenv("LDAP_BIND_PASSWORD", None),
        ldap_group_base_dn=ldap_group_base_dn,
        ldap_group_filter=ldap_group_filter,
        ldap_group_name_attr=os.getenv("LDAP_GROUP_NAME_ATTR", "cn"),
        ldap_host=ldap_host,
        ldap_port=int(os.getenv("LDAP_PORT", 389)),
        ldap_user_base_dn=ldap_user_base_dn,
        ldap_user_filter=ldap_user_filter,
        ldap_user_name_attr=os.getenv("LDAP_USER_NAME_ATTR", "userPrincipalName"),
        postgresql_database_name=os.getenv("POSTGRESQL_DB_NAME", "guacamole"),
        postgresql_host_name=postgresql_host_name,
        postgresql_password=postgresql_password,
        postgresql_port=int(os.getenv("POSTGRESQL_PORT", 5432)),
        postgresql_user_name=postgresql_user_name,
        repeat_interval=int(os.getenv("REPEAT_INTERVAL", 300)),
    )
