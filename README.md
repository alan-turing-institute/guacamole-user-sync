# guacamole-user-sync
Synchronise a Guacamole PostgreSQL database with an LDAP server, such as Microsoft Active Directory

[![Latest image](https://ghcr-badge.egpl.dev/alan-turing-institute/guacamole-user-sync/latest_tag)](https://github.com/alan-turing-institute/guacamole-user-sync/pkgs/container/guacamole-user-sync)
[![Image size](https://ghcr-badge.egpl.dev/alan-turing-institute/guacamole-user-sync/size)](https://github.com/alan-turing-institute/guacamole-user-sync/pkgs/container/guacamole-user-sync)
[![Publish status](https://github.com/alan-turing-institute/guacamole-user-sync/actions/workflows/publish_docker.yaml/badge.svg)](https://github.com/alan-turing-institute/guacamole-user-sync/pkgs/)

## Running with Docker

You can run this Docker image as follows

```console
$ docker run -it \
    -e LDAP_HOST=$(your LDAP server host) \
    -e LDAP_GROUP_BASE_DN=$(your LDAP group DN) \
    -e LDAP_GROUP_FILTER=$(your LDAP group filter) \
    -e LDAP_USER_BASE_DN=$(your LDAP user DN) \
    -e LDAP_USER_FILTER=$(your LDAP user filter) \
    -e POSTGRESQL_HOST=$(your PostgreSQL server host) \
    -e POSTGRESQL_PASSWORD=$(your PostgreSQL connection password) \
    -e POSTGRESQL_USERNAME=$(your PostgreSQL connection username) \
    ghcr.io/alan-turing-institute/guacamole-user-sync:$(version you want to use)
```

LDAP filter syntax is described here: https://ldap.com/ldap-filters/.
If you want a simple filter for testing, try `(objectClass=*)` which will match any LDAP object.

Similarly, LDAP distinguished names (DNs) are described here: https://ldap.com/ldap-dns-and-rdns/.
The user or group base DN will typically be the organisational unit (OU) that all objects of that type belong to.
For example, a simple user base DN might look something like `OU=users,DC=example,DC=com`.

## Environment variables

- `DEBUG`: Enable debug output (default: 'False')
- `LDAP_BIND_DN`: (Optional) distinguished name of LDAP bind user
- `LDAP_BIND_PASSWORD`: (Optional) password of LDAP bind user
- `LDAP_GROUP_BASE_DN`: Base DN for groups
- `LDAP_GROUP_FILTER`: LDAP filter to select groups
- `LDAP_GROUP_NAME_ATTR`: Attribute used to extract group names (default: 'cn')
- `LDAP_HOST`: LDAP host
- `LDAP_PORT`: LDAP port (default: '389')
- `LDAP_USER_BASE_DN`: Base DN for users
- `LDAP_USER_FILTER`: LDAP filter to select users
- `LDAP_USER_NAME_ATTR`: Attribute used to extract user names (default: 'userPrincipalName')
- `POSTGRESQL_DB_NAME`: Database name for PostgreSQL server (default: 'guacamole')
- `POSTGRESQL_HOST`: PostgreSQL server host
- `POSTGRESQL_PASSWORD`: Password of PostgreSQL user
- `POSTGRESQL_PORT`: PostgreSQL server port (default: '5432')
- `POSTGRESQL_USERNAME`: Username of PostgreSQL user
- `REPEAT_INTERVAL`: How often (in seconds) to wait before attempting to synchronise again (default: '300')

## Contributing

Pull requests are always welcome.

### Running with Docker

Build the Docker image with

```console
$ docker build . -t guacamole-user-sync
```

Run the Docker image you have just built with

```console
$ docker run -it \
    -e LDAP_HOST=$(your LDAP server host) \
    -e LDAP_GROUP_BASE_DN=$(your LDAP group DN) \
    -e LDAP_GROUP_FILTER=$(your LDAP group filter) \
    -e LDAP_USER_BASE_DN=$(your LDAP user DN) \
    -e LDAP_USER_FILTER=$(your LDAP user filter) \
    -e POSTGRESQL_HOST=$(your PostgreSQL server host) \
    -e POSTGRESQL_PASSWORD=$(your PostgreSQL connection password) \
    -e POSTGRESQL_USERNAME=$(your PostgreSQL connection username) \
    guacamole-user-sync
```

### Tests

In order to run the tests, you should install the following prerequisites:

- [`hatch`](https://hatch.pypa.io/latest/install/)

The tests can then be run with

```console
$ hatch run test:all
```
