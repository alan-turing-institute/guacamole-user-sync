#! /usr/bin/env python3
import logging
import os
import time

from guacamole_user_sync import LDAPClient

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format=r"%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt=r"%Y-%m-%d %H:%M:%S",
)


def main(ldap_host: str, repeat_interval: int):
    logger.info("Starting synchronisation.")
    client = LDAPClient(ldap_host)
    synchronise(client)
    logger.info(f"Waiting {repeat_interval} seconds.")
    time.sleep(repeat_interval)


def synchronise(client: LDAPClient):
    logger.info("Synchronising...")
    logger.info(f"client {str(client)}")


if __name__ == "__main__":
    if not (ldap_host := os.getenv("LDAP_HOST", None)):
        raise ValueError("LDAP_HOST is not defined")
    main(
        ldap_host=f"{ldap_host}:{os.getenv("LDAP_PORT", 389)}",
        repeat_interval=int(os.getenv("REPEAT_INTERVAL", 10)),
    )
