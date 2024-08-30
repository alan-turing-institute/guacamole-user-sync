import logging

from ldap.ldapobject import LDAPObject
from ldap.asyncsearch import List as AsyncSearchList
import ldap

from guacamole_user_sync.models import LDAPQuery, LDAPUser

logger = logging.getLogger("guacamole_user_sync")

LDAPSearchResult = list[tuple[int, tuple[str, dict[str, list[bytes]]]]]


class LDAPClient:
    def __init__(self, hostname: str) -> None:
        self.hostname = hostname
        self._host = None

    @property
    def host(self) -> LDAPObject:
        if not self._host:
            logger.info(f"Initialising connection to LDAP host at {self.hostname}")
            self._host = ldap.initialize(f"ldap://{self.hostname}")
        return self._host

    def search_users(self, query: LDAPQuery) -> list[LDAPUser]:
        output = []
        for result in self.search(query):
            attr_dict = result[1][1]
            output.append(
                LDAPUser(
                    dn=result[1][0],
                    cn=attr_dict["cn"][0].decode("utf-8"),
                    description=attr_dict["description"][0].decode("utf-8"),
                    displayName=attr_dict["displayName"][0].decode("utf-8"),
                    gidNumber=int(attr_dict["gidNumber"][0].decode("utf-8")),
                    givenName=attr_dict["givenName"][0].decode("utf-8"),
                    homeDirectory=attr_dict["homeDirectory"][0].decode("utf-8"),
                    memberOf=[group.decode("utf-8") for group in attr_dict["memberOf"]],
                    objectClass=[
                        objc.decode("utf-8") for objc in attr_dict["objectClass"]
                    ],
                    sn=attr_dict["sn"][0].decode("utf-8"),
                    uid=attr_dict["uid"][0].decode("utf-8"),
                    uidNumber=int(attr_dict["uidNumber"][0].decode("utf-8")),
                )
            )
        return output

    def search(self, query: LDAPQuery) -> LDAPSearchResult:
        results: LDAPSearchResult = []
        logger.info("Querying LDAP host with:")
        logger.info(f"... base DN: {query.base_dn}")
        logger.info(f"... filter: {query.filter}")
        searcher = AsyncSearchList(self.host)
        try:
            searcher.startSearch(
                query.base_dn,
                ldap.SCOPE_SUBTREE,
                query.filter,
            )
            partial = searcher.processResults()
            if partial:
                logger.warning("Only partial results received.")
        except ldap.SERVER_DOWN:
            logger.warning("Server could not be reached.")
            return results
        except ldap.SIZELIMIT_EXCEEDED:
            logger.warning("Server-side size limit exceeded.")
            return results

        results = searcher.allResults
        logger.debug(f"Server returned {len(results)} results.")
        return results
