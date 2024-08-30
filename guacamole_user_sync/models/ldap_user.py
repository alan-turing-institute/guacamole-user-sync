from dataclasses import dataclass


@dataclass
class LDAPUser:
    """An LDAP user with attributes."""

    cn: str
    description: str
    displayName: str
    dn: str
    gidNumber: int
    givenName: str
    homeDirectory: str
    memberOf: list[str]
    objectClass: list[str]
    sn: str
    uid: str
    uidNumber: int
