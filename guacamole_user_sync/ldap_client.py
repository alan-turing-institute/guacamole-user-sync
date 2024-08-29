from ldap.ldapobject import LDAPObject
import ldap

class LDAPClient:
    def __init__(self, hostname) -> None:
        self.hostname = hostname

    @property
    def host(self) -> LDAPObject:
        return ldap.initialize(f"ldap://{self.hostname}")