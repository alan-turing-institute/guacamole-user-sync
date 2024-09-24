from .exceptions import LDAPError, PostgreSQLError
from .ldap_objects import LDAPGroup, LDAPUser
from .ldap_query import LDAPQuery

LDAPSearchResult = list[tuple[int, tuple[str, dict[str, list[bytes]]]]]

__all__ = [
    "LDAPError",
    "LDAPGroup",
    "LDAPQuery",
    "LDAPSearchResult",
    "LDAPUser",
    "PostgreSQLError",
]
