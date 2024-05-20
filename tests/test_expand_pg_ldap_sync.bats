# bats file_tags=ruby:expand_pg_ldap_sync

setup() {
    touch test_output.yaml
    # get the containing directory of this file using $BATS_TEST_FILENAME
    # instead of ${BASH_SOURCE[0]} or $0, as those will point to the bats
    # executable's location or the preprocessed file respectively
    TEST_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" >/dev/null 2>&1 && pwd)"
}


check_success() {
  if (( status )); then
    echo $output
    return 1
  fi
}

check_failure() {
  if (( ! status )); then
    echo $output
    return 1
  fi
}

test_expansion() {
    rm test_output.yaml
    ${TEST_DIR}/../scripts/expand_pg_ldap_sync.rb > test_output.yaml
    grep "$1" test_output.yaml && return
    echo "Failed to find '$1' in expanded output"
    cat test_output.yaml
    return 1
}

@test "Test setting LDAP_BIND_DN" {
  export LDAP_BIND_DN="CN=user,DC=example,DC=com"
  run test_expansion 'username: "CN=user,DC=example,DC=com"'
  export -n LDAP_BIND_DN
  check_success
}

@test "Test setting LDAP_BIND_PASSWORD only" {
  export LDAP_BIND_PASSWORD="!a#b$c"
  run test_expansion 'password: "!a#b$c"'
  export -n LDAP_BIND_PASSWORD
  check_failure
}

@test "Test setting LDAP_BIND_PASSWORD with LDAP_BIND_DN" {
  export LDAP_BIND_DN="CN=user,DC=example,DC=com"
  export LDAP_BIND_PASSWORD="!a#b%c"
  run test_expansion 'password: "!a#b%c"'
  export -n LDAP_BIND_DN LDAP_BIND_PASSWORD
  check_success
}

@test "Test setting LDAP_GROUP_BASE_DN" {
  export LDAP_GROUP_BASE_DN="OU=groups,DC=example,DC=com"
  run test_expansion 'base: "OU=groups,DC=example,DC=com"'
  export -n LDAP_GROUP_BASE_DN
  check_success
}

@test "Test setting LDAP_GROUP_FILTER" {
  export LDAP_GROUP_FILTER="(objectClass=posixGroup)"
  run test_expansion 'filter: "(objectClass=posixGroup)"'
  export -n LDAP_GROUP_FILTER
  check_success
}

@test "Test setting LDAP_GROUP_NAME_ATTR" {
  export LDAP_GROUP_NAME_ATTR="samAccountName"
  run test_expansion 'name_attribute: "samAccountName"'
  export -n LDAP_GROUP_NAME_ATTR
  check_success
}

@test "Test default LDAP_GROUP_NAME_ATTR" {
  export -n LDAP_GROUP_NAME_ATTR
  run test_expansion 'name_attribute: "cn"'
  check_success
}

@test "Test setting LDAP_HOST" {
  export LDAP_HOST="ldap.example.com"
  run test_expansion 'host: "ldap.example.com"'
  export -n LDAP_HOST
  check_success
}

@test "Test setting LDAP_PORT" {
  export LDAP_PORT="1234"
  run test_expansion 'port: "1234"'
  export -n LDAP_PORT
  check_success
}

@test "Test default LDAP_PORT" {
  export -n LDAP_PORT
  run test_expansion 'port: "389"'
  check_success
}

@test "Test setting LDAP_USER_BASE_DN" {
  export LDAP_USER_BASE_DN="OU=users,DC=example,DC=com"
  run test_expansion 'base: "OU=users,DC=example,DC=com"'
  export -n LDAP_USER_BASE_DN
  check_success
}

@test "Test setting LDAP_USER_FILTER" {
  export LDAP_USER_FILTER="(objectClass=posixAccount)"
  run test_expansion 'filter: "(objectClass=posixAccount)"'
  export -n LDAP_USER_FILTER
  check_success
}

@test "Test setting LDAP_USER_NAME_ATTR" {
  export LDAP_USER_NAME_ATTR="samAccountName"
  run test_expansion 'name_attribute: "samAccountName"'
  export -n LDAP_USER_NAME_ATTR
  check_success
}

@test "Test default LDAP_USER_NAME_ATTR" {
  export -n LDAP_USER_NAME_ATTR
  run test_expansion 'name_attribute: "userPrincipalName"'
  check_success
}

@test "Test setting POSTGRESQL_DB_NAME" {
  export POSTGRESQL_DB_NAME="db-names"
  run test_expansion 'dbname: "db-names"'
  export -n POSTGRESQL_DB_NAME
  check_success
}

@test "Test default POSTGRESQL_DB_NAME" {
  export -n POSTGRESQL_DB_NAME
  run test_expansion 'dbname: "guacamole"'
  check_success
}

@test "Test setting POSTGRESQL_HOST" {
  export POSTGRESQL_HOST="postgresql.example.com"
  run test_expansion 'host: "postgresql.example.com"'
  export -n POSTGRESQL_HOST
  check_success
}

@test "Test setting POSTGRESQL_PASSWORD" {
  export POSTGRESQL_PASSWORD="!a#b%c"
  run test_expansion 'password: "!a#b%c"'
  export -n POSTGRESQL_PASSWORD
  check_success
}

@test "Test setting POSTGRESQL_PORT" {
  export POSTGRESQL_PORT="1234"
  run test_expansion 'port: "1234"'
  export -n POSTGRESQL_PORT
  check_success
}

@test "Test default POSTGRESQL_PORT" {
  export -n POSTGRESQL_PORT
  run test_expansion 'port: "5432"'
  check_success
}

@test "Test setting POSTGRESQL_USERNAME" {
  export POSTGRESQL_USERNAME="psqladmin"
  run test_expansion 'user: "psqladmin"'
  export -n POSTGRESQL_USERNAME
  check_success
}

teardown() {
  rm test_output.yaml
}