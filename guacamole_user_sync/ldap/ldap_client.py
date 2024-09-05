import logging

import ldap
from ldap.asyncsearch import List as AsyncSearchList
from ldap.ldapobject import LDAPObject

from guacamole_user_sync.models import LDAPException, LDAPGroup, LDAPQuery, LDAPUser

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

    def search_groups(self, query: LDAPQuery) -> list[LDAPGroup]:
        output = []
        for result in self.search(query):
            logger.info(result)
            attr_dict = result[1][1]
            output.append(
                LDAPGroup(
                    dn=result[1][0],
                    cn=attr_dict["cn"][0].decode("utf-8"),
                    description=attr_dict["description"][0].decode("utf-8"),
                    gid_number=int(attr_dict["gidNumber"][0].decode("utf-8")),
                    member=[group.decode("utf-8") for group in attr_dict["member"]],
                    member_of=[
                        group.decode("utf-8") for group in attr_dict["memberOf"]
                    ],
                    member_uid=[
                        group.decode("utf-8") for group in attr_dict["memberUid"]
                    ],
                    name=attr_dict[query.id_attr][0].decode("utf-8"),
                    object_class=[
                        objc.decode("utf-8") for objc in attr_dict["objectClass"]
                    ],
                )
            )
        return output

    def search_users(self, query: LDAPQuery) -> list[LDAPUser]:
        output = []
        for result in self.search(query):
            attr_dict = result[1][1]
            output.append(
                LDAPUser(
                    dn=result[1][0],
                    cn=attr_dict["cn"][0].decode("utf-8"),
                    description=attr_dict["description"][0].decode("utf-8"),
                    display_name=attr_dict["displayName"][0].decode("utf-8"),
                    gid_number=int(attr_dict["gidNumber"][0].decode("utf-8")),
                    given_name=attr_dict["givenName"][0].decode("utf-8"),
                    home_directory=attr_dict["homeDirectory"][0].decode("utf-8"),
                    member_of=[
                        group.decode("utf-8") for group in attr_dict["memberOf"]
                    ],
                    name=attr_dict[query.id_attr][0].decode("utf-8"),
                    object_class=[
                        objc.decode("utf-8") for objc in attr_dict["objectClass"]
                    ],
                    sn=attr_dict["sn"][0].decode("utf-8"),
                    uid=attr_dict["uid"][0].decode("utf-8"),
                    uid_number=int(attr_dict["uidNumber"][0].decode("utf-8")),
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
        except ldap.SERVER_DOWN as exc:
            logger.warning("Server could not be reached.")
            raise LDAPException from exc
        except ldap.SIZELIMIT_EXCEEDED as exc:
            logger.warning("Server-side size limit exceeded.")
            raise LDAPException from exc

        results = searcher.allResults
        logger.debug(f"Server returned {len(results)} results.")
        return results
