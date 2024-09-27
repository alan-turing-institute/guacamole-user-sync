import logging
from typing import cast

from ldap3 import ALL, ALL_ATTRIBUTES, Connection, Server
from ldap3.abstract.entry import Entry
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPSessionTerminatedByServerError,
    LDAPSocketOpenError,
)

from guacamole_user_sync.models import (
    LDAPError,
    LDAPGroup,
    LDAPQuery,
    LDAPUser,
)

logger = logging.getLogger("guacamole_user_sync")


class LDAPClient:
    """Client for connecting to an LDAP server."""

    def __init__(
        self,
        hostname: str,
        *,
        bind_dn: str | None = None,
        bind_password: str | None = None,
    ) -> None:
        self.bind_dn = bind_dn
        self.bind_password = bind_password
        self.hostname = hostname

    @staticmethod
    def as_list(ldap_entry: str | list[str] | None) -> list[str]:
        if isinstance(ldap_entry, list):
            return ldap_entry
        if ldap_entry is None:
            return []
        if isinstance(ldap_entry, str):
            return [ldap_entry]
        msg = f"Unexpected input {ldap_entry} of type {type(ldap_entry)}"
        raise ValueError(msg)

    def connect(self) -> Connection:
        logger.info("Initialising connection to LDAP host at %s", self.hostname)
        try:
            server = Server(self.hostname, get_info=ALL)
            if self.bind_dn:
                return Connection(
                    server,
                    self.bind_dn,
                    self.bind_password,
                    auto_bind=True,
                )
            return Connection(server, auto_bind=True)
        except LDAPBindError as exc:
            logger.warning("Connection credentials were incorrect.")
            raise LDAPError from exc

    def search_groups(self, query: LDAPQuery) -> list[LDAPGroup]:
        output = []
        for entry in self.search(query):
            output.append(
                LDAPGroup(
                    member_of=self.as_list(entry.memberOf.value),
                    member_uid=self.as_list(entry.memberUid.value),
                    name=getattr(entry, query.id_attr).value,
                ),
            )
            logger.debug("Found LDAP group %s", output[-1])
        logger.debug("Loaded %s LDAP groups", len(output))
        return output

    def search_users(self, query: LDAPQuery) -> list[LDAPUser]:
        output = []
        for entry in self.search(query):
            output.append(
                LDAPUser(
                    display_name=entry.displayName.value,
                    member_of=self.as_list(entry.memberOf.value),
                    name=getattr(entry, query.id_attr).value,
                    uid=entry.uid.value,
                ),
            )
            logger.debug("Found LDAP user %s", output[-1])
        logger.debug("Loaded %s LDAP users", len(output))
        return output

    def search(self, query: LDAPQuery) -> list[Entry]:
        logger.info("Querying LDAP host with:")
        logger.info("... base DN: %s", query.base_dn)
        logger.info("... filter: %s", query.filter)
        try:
            connection = self.connect()
            connection.search(query.base_dn, query.filter, attributes=ALL_ATTRIBUTES)
        except LDAPSocketOpenError as exc:
            logger.warning("Server could not be reached.")
            raise LDAPError from exc

        except LDAPSessionTerminatedByServerError as exc:
            logger.warning("Server terminated LDAP request.")
            raise LDAPError from exc
        else:
            results = cast(list[Entry], connection.entries)
            logger.debug("Server returned %s results.", len(results))
            return results
