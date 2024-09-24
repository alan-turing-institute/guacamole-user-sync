from .exceptions import LDAPException, PostgreSQLException
from .ldap_objects import LDAPGroup, LDAPUser
from .ldap_query import LDAPQuery

LDAPSearchResult = list[tuple[int, tuple[str, dict[str, list[bytes]]]]]

__all__ = [
    "LDAPException",
    "LDAPGroup",
    "LDAPQuery",
    "LDAPSearchResult",
    "LDAPUser",
    "PostgreSQLException",
]
