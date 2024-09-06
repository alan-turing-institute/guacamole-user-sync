from dataclasses import dataclass


@dataclass
class LDAPGroup:
    """An LDAP group with required attributes only."""

    member_of: list[str]
    member_uid: list[str]
    name: str


@dataclass
class LDAPUser:
    """An LDAP user with required attributes only."""

    display_name: str
    member_of: list[str]
    name: str
    uid: str
