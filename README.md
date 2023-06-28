# guacamole-user-sync
Synchronise a Guacamole PostgreSQL database with a Microsoft Active Directory

## Environment variables

- LDAP_BIND_DN: Distinguished name of LDAP bind user
- LDAP_BIND_PASSWORD: Password of LDAP bind user
- LDAP_GROUP_BASE_DN: Base DN for groups
- LDAP_GROUP_FILTER: LDAP filter to select groups
- LDAP_HOST: LDAP host
- LDAP_USER_BASE_DN: Base DN for users
- LDAP_USER_FILTER: LDAP filter to select users
- POSTGRES_DB_NAME: Database name for PostgreSQL server (default: 'guacamole')
- POSTGRES_HOST: PostgreSQL server host
- POSTGRES_PASSWORD: Password of PostgreSQL user
- POSTGRES_PORT: PostgreSQL server port (default: '5432')
- POSTGRES_USERNAME: Username of PostgreSQL user
