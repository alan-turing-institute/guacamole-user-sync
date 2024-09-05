from dataclasses import dataclass


@dataclass
class LDAPGroup:
    """An LDAP group with attributes."""

    cn: str
    description: str
    dn: str
    gid_number: int
    member: list[str]
    member_of: list[str]
    member_uid: list[str]
    name: str
    object_class: list[str]


@dataclass
class LDAPUser:
    """An LDAP user with attributes."""

    cn: str
    description: str
    display_name: str
    dn: str
    gid_number: int
    given_name: str
    home_directory: str
    member_of: list[str]
    name: str
    object_class: list[str]
    sn: str
    uid: str
    uid_number: int
