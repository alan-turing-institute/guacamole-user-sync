import logging

import ldap
from ldap.asyncsearch import List as AsyncSearchList
from ldap.ldapobject import LDAPObject

from guacamole_user_sync.models import (
    LDAPError,
    LDAPGroup,
    LDAPQuery,
    LDAPSearchResult,
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
        self.cnxn: LDAPObject | None = None
        self.bind_dn = bind_dn
        self.bind_password = bind_password
        self.hostname = hostname

    def connect(self) -> LDAPObject:
        if not self.cnxn:
            logger.info(f"Initialising connection to LDAP host at {self.hostname}")
            self.cnxn = ldap.initialize(f"ldap://{self.hostname}")
            if self.bind_dn:
                try:
                    self.cnxn.simple_bind_s(self.bind_dn, self.bind_password)
                except ldap.INVALID_CREDENTIALS as exc:
                    logger.warning("Connection credentials were incorrect.")
                    raise LDAPError from exc
        return self.cnxn

    def search_groups(self, query: LDAPQuery) -> list[LDAPGroup]:
        output = []
        for result in self.search(query):
            attr_dict = result[1][1]
            output.append(
                LDAPGroup(
                    member_of=[
                        group.decode("utf-8") for group in attr_dict["memberOf"]
                    ],
                    member_uid=[
                        group.decode("utf-8") for group in attr_dict["memberUid"]
                    ],
                    name=attr_dict[query.id_attr][0].decode("utf-8"),
                ),
            )
        logger.debug(f"Loaded {len(output)} LDAP groups")
        return output

    def search_users(self, query: LDAPQuery) -> list[LDAPUser]:
        output = []
        for result in self.search(query):
            attr_dict = result[1][1]
            output.append(
                LDAPUser(
                    display_name=attr_dict["displayName"][0].decode("utf-8"),
                    member_of=[
                        group.decode("utf-8") for group in attr_dict["memberOf"]
                    ],
                    name=attr_dict[query.id_attr][0].decode("utf-8"),
                    uid=attr_dict["uid"][0].decode("utf-8"),
                ),
            )
        logger.debug(f"Loaded {len(output)} LDAP users")
        return output

    def search(self, query: LDAPQuery) -> LDAPSearchResult:
        results: LDAPSearchResult = []
        logger.info("Querying LDAP host with:")
        logger.info(f"... base DN: {query.base_dn}")
        logger.info(f"... filter: {query.filter}")
        searcher = AsyncSearchList(self.connect())
        try:
            searcher.startSearch(
                query.base_dn,
                ldap.SCOPE_SUBTREE,
                query.filter,
            )
            if searcher.processResults() != 0:
                logger.warning("Only partial results received.")
            results = searcher.allResults
            logger.debug(f"Server returned {len(results)} results.")
            return results
        except ldap.NO_SUCH_OBJECT as exc:
            logger.warning("Server returned no results.")
            raise LDAPError from exc
        except ldap.SERVER_DOWN as exc:
            logger.warning("Server could not be reached.")
            raise LDAPError from exc
        except ldap.SIZELIMIT_EXCEEDED as exc:
            logger.warning("Server-side size limit exceeded.")
            raise LDAPError from exc
