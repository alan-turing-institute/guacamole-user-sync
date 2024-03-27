# guacamole-user-sync
Synchronise a Guacamole PostgreSQL database with an LDAP server, such as Microsoft Active Directory

## Environment variables

- LDAP_BIND_DN: (Optional) distinguished name of LDAP bind user
- LDAP_BIND_PASSWORD: (Optional) password of LDAP bind user
- LDAP_GROUP_BASE_DN: Base DN for groups
- LDAP_GROUP_FILTER: LDAP filter to select groups
- LDAP_HOST: LDAP host
- LDAP_PORT: LDAP port
- LDAP_USER_BASE_DN: Base DN for users
- LDAP_USER_FILTER: LDAP filter to select users
- POSTGRESQL_DB_NAME: Database name for PostgreSQL server (default: 'guacamole')
- POSTGRESQL_HOST: PostgreSQL server host
- POSTGRESQL_PASSWORD: Password of PostgreSQL user
- POSTGRESQL_PORT: PostgreSQL server port (default: '5432')
- POSTGRESQL_USERNAME: Username of PostgreSQL user
- REPEAT_INTERVAL: How often (in seconds) to wait before attempting to synchronise again (default: '300')
