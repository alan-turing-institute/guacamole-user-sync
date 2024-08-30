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
    ldap_host: str,
    ldap_port: int,
    ldap_user_base_dn: str,
    ldap_user_filter: str,
    ldap_user_name_attr: str,
    repeat_interval: int,
) -> None:
    # Initialise LDAP client
    ldap_client = LDAPClient(f"{ldap_host}:{ldap_port}")
    ldap_user_query = LDAPQuery(
        base_dn=ldap_user_base_dn,
        filter=ldap_user_filter,
        id_attr=os.getenv("LDAP_USER_NAME_ATTR", "userPrincipalName"),
    )

    # Loop until terminated
    while True:
        # Run synchronisation step
        synchronise(ldap_client, ldap_user_query)

        # Wait before repeating
        logger.info(f"Waiting {repeat_interval} seconds.")
        time.sleep(repeat_interval)


def synchronise(client: LDAPClient, ldap_user_query: LDAPQuery) -> None:
    logger.info("Starting synchronisation.")
    client.search(ldap_user_query)


if __name__ == "__main__":
    if not (ldap_host := os.getenv("LDAP_HOST", None)):
        raise ValueError("LDAP_HOST is not defined")
    if not (ldap_user_base_dn := os.getenv("LDAP_USER_BASE_DN", None)):
        raise ValueError("LDAP_USER_BASE_DN is not defined")
    if not (ldap_user_filter := os.getenv("LDAP_USER_FILTER", None)):
        raise ValueError("LDAP_USER_FILTER is not defined")

    main(
        ldap_host=ldap_host,
        ldap_port=int(os.getenv("LDAP_PORT", 389)),
        ldap_user_base_dn=ldap_user_base_dn,
        ldap_user_filter=ldap_user_filter,
        ldap_user_name_attr=os.getenv("LDAP_USER_NAME_ATTR", "userPrincipalName"),
        repeat_interval=int(os.getenv("REPEAT_INTERVAL", 10)),
    )
