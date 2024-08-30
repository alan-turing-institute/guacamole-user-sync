#! /usr/bin/env python3
import logging
import os
import time

from guacamole_user_sync import LDAPClient, LDAPQuery

logger = logging.getLogger("guacamole_user_sync")
logging.basicConfig(
    level=logging.INFO,
    format=r"%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt=r"%Y-%m-%d %H:%M:%S",
)


def main(
    ldap_group_base_dn: str,
    ldap_group_filter: str,
    ldap_group_name_attr: str,
    ldap_host: str,
    ldap_port: int,
    ldap_user_base_dn: str,
    ldap_user_filter: str,
    ldap_user_name_attr: str,
    repeat_interval: int,
) -> None:
    # Initialise LDAP resources
    ldap_client = LDAPClient(f"{ldap_host}:{ldap_port}")
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

    # Loop until terminated
    while True:
        # Run synchronisation step
        synchronise(
            ldap_client,
            ldap_group_query=ldap_group_query,
            ldap_user_query=ldap_user_query,
        )

        # Wait before repeating
        logger.info(f"Waiting {repeat_interval} seconds.")
        time.sleep(repeat_interval)


def synchronise(
    client: LDAPClient, *, ldap_group_query: LDAPQuery, ldap_user_query: LDAPQuery
) -> None:
    logger.info("Starting synchronisation.")
    ldap_groups = client.search_groups(ldap_group_query)
    for ldap_group in ldap_groups:
        logger.info(f"ldap_group: {ldap_group}")
    ldap_users = client.search_users(ldap_user_query)
    for ldap_user in ldap_users:
        logger.info(f"ldap_user: {ldap_user}")


if __name__ == "__main__":
    if not (ldap_host := os.getenv("LDAP_HOST", None)):
        raise ValueError("LDAP_HOST is not defined")
    if not (ldap_group_base_dn := os.getenv("LDAP_GROUP_BASE_DN", None)):
        raise ValueError("LDAP_GROUP_BASE_DN is not defined")
    if not (ldap_group_filter := os.getenv("LDAP_GROUP_FILTER", None)):
        raise ValueError("LDAP_GROUP_FILTER is not defined")

    if not (ldap_user_base_dn := os.getenv("LDAP_USER_BASE_DN", None)):
        raise ValueError("LDAP_USER_BASE_DN is not defined")
    if not (ldap_user_filter := os.getenv("LDAP_USER_FILTER", None)):
        raise ValueError("LDAP_USER_FILTER is not defined")

    main(
        ldap_group_base_dn=ldap_group_base_dn,
        ldap_group_filter=ldap_group_filter,
        ldap_group_name_attr=os.getenv("LDAP_GROUP_NAME_ATTR", "cn"),
        ldap_host=ldap_host,
        ldap_port=int(os.getenv("LDAP_PORT", 389)),
        ldap_user_base_dn=ldap_user_base_dn,
        ldap_user_filter=ldap_user_filter,
        ldap_user_name_attr=os.getenv("LDAP_USER_NAME_ATTR", "userPrincipalName"),
        repeat_interval=int(os.getenv("REPEAT_INTERVAL", 10)),
    )
