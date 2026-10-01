import logging
from typing import cast

from ldap3 import ALL, ALL_ATTRIBUTES, Connection, Server
from ldap3.abstract.entry import Entry
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPException,
    LDAPInvalidDnError,
    LDAPSessionTerminatedByServerError,
    LDAPSocketOpenError,
)
from ldap3.utils.dn import parse_dn

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
        auto_bind: bool = True,
        bind_dn: str | None = None,
        bind_password: str | None = None,
        group_member_attribute: str = "memberUid",
    ) -> None:
        self.auto_bind = auto_bind
        self.bind_dn = bind_dn
        self.bind_password = bind_password
        self.group_member_attribute = group_member_attribute
        self.server = Server(hostname, get_info=ALL)

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

    @staticmethod
    def member_uid(member: str) -> str:
        """Return a UID from either a plain member value or a UID-based DN."""
        if "=" not in member:
            return member
        try:
            parsed_dn = cast(
                list[tuple[str, str, str]],
                parse_dn(member, escape=True, strip=True),
            )
        except LDAPInvalidDnError:
            return member
        if parsed_dn and parsed_dn[0][0].casefold() == "uid":
            return parsed_dn[0][1]
        return member

    def connect(self) -> Connection:
        logger.info("Initialising connection to LDAP host at %s", self.server.host)
        try:
            return Connection(
                self.server,
                user=self.bind_dn,
                password=self.bind_password,
                auto_bind=self.auto_bind,
            )
        except LDAPSocketOpenError as exc:
            msg = "Server could not be reached."
            logger.error(msg)  # noqa: TRY400
            raise LDAPError(msg) from exc
        except LDAPBindError as exc:
            msg = "Connection credentials were incorrect."
            logger.error(msg)  # noqa: TRY400
            raise LDAPError(msg) from exc
        except LDAPException as exc:
            msg = f"Unexpected LDAP exception of type {type(exc)}."
            logger.error(msg)  # noqa: TRY400
            raise LDAPError(msg) from exc

    def search_groups(self, query: LDAPQuery) -> list[LDAPGroup]:
        output = []
        for entry in self.search(query):
            member_of_attr = getattr(entry, "memberOf", None)
            member_attr = getattr(entry, self.group_member_attribute, None)
            group_members = self.as_list(member_attr.value if member_attr else None)
            output.append(
                LDAPGroup(
                    member_of=self.as_list(
                        member_of_attr.value if member_of_attr else None,
                    ),
                    member_uid=[self.member_uid(member) for member in group_members],
                    name=getattr(entry, query.id_attr).value,
                ),
            )
            logger.debug("Found LDAP group %s", output[-1])
        logger.debug("Loaded %s LDAP groups", len(output))
        return output

    def search_users(self, query: LDAPQuery) -> list[LDAPUser]:
        output = []
        for entry in self.search(query):
            display_name_attr = getattr(entry, "displayName", None)
            member_of_attr = getattr(entry, "memberOf", None)
            uid_attr = getattr(entry, "uid", None)
            output.append(
                LDAPUser(
                    display_name=display_name_attr.value if display_name_attr else "",
                    member_of=self.as_list(
                        member_of_attr.value if member_of_attr else None,
                    ),
                    name=getattr(entry, query.id_attr).value,
                    uid=uid_attr.value if uid_attr else "",
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
        except LDAPSessionTerminatedByServerError as exc:
            msg = "Server terminated LDAP request."
            logger.error(msg)  # noqa: TRY400
            raise LDAPError(msg) from exc
        except LDAPException as exc:
            msg = f"Unexpected LDAP exception of type {type(exc)}."
            logger.error(msg)  # noqa: TRY400
            raise LDAPError(msg) from exc
        else:
            results = cast(list[Entry], connection.entries)
            logger.debug("Server returned %s results.", len(results))
            return results
