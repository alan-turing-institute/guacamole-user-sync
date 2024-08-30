from dataclasses import dataclass


@dataclass
class LDAPQuery:
    """An LDAP query with attributes."""

    base_dn: str
    filter: str
    id_attr: str
