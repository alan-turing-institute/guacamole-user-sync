#! /usr/bin/env bats
# bats file_tags=ruby:expand_pg_ldap_sync

setup() {
  load 'common'
  common_setup
}

query_pg_ldap_sync() {
  query_string="$1"
  ${TEST_DIR}/../scripts/expand_pg_ldap_sync.rb | yq eval "$query_string"
}

@test "Test setting LDAP_BIND_DN" {
  export LDAP_BIND_DN="CN=user,DC=example,DC=com"
  run query_pg_ldap_sync ".ldap_connection.auth.username"
  export -n LDAP_BIND_DN
  assert_output "CN=user,DC=example,DC=com"
}

@test "Test setting LDAP_BIND_PASSWORD only" {
  export LDAP_BIND_PASSWORD="!a#b%c"
  run query_pg_ldap_sync ".ldap_connection.auth.password"
  export -n LDAP_BIND_PASSWORD
  assert_output null
}

@test "Test setting LDAP_BIND_PASSWORD with LDAP_BIND_DN" {
  export LDAP_BIND_DN="CN=user,DC=example,DC=com"
  export LDAP_BIND_PASSWORD="!a#b%c"
  run query_pg_ldap_sync ".ldap_connection.auth.password"
  export -n LDAP_BIND_DN LDAP_BIND_PASSWORD
  assert_output "!a#b%c"
}

@test "Test setting LDAP_GROUP_BASE_DN" {
  export LDAP_GROUP_BASE_DN="OU=groups,DC=example,DC=com"
  run query_pg_ldap_sync ".ldap_groups.base"
  export -n LDAP_GROUP_BASE_DN
  assert_output "OU=groups,DC=example,DC=com"
}

@test "Test setting LDAP_GROUP_FILTER" {
  export LDAP_GROUP_FILTER="(objectClass=posixGroup)"
  run query_pg_ldap_sync ".ldap_groups.filter"
  export -n LDAP_GROUP_FILTER
  assert_output "(objectClass=posixGroup)"
}

@test "Test setting LDAP_GROUP_NAME_ATTR" {
  export LDAP_GROUP_NAME_ATTR="samAccountName"
  run query_pg_ldap_sync ".ldap_groups.name_attribute"
  export -n LDAP_GROUP_NAME_ATTR
  assert_output "samAccountName"
}

@test "Test default LDAP_GROUP_NAME_ATTR" {
  export -n LDAP_GROUP_NAME_ATTR
  run query_pg_ldap_sync ".ldap_groups.name_attribute"
  assert_output "cn"
}

@test "Test setting LDAP_HOST" {
  export LDAP_HOST="ldap.example.com"
  run query_pg_ldap_sync ".ldap_connection.host"
  export -n LDAP_HOST
  assert_output "ldap.example.com"
}

@test "Test setting LDAP_PORT" {
  export LDAP_PORT="1234"
  run query_pg_ldap_sync ".ldap_connection.port"
  export -n LDAP_PORT
  assert_output "1234"
}

@test "Test default LDAP_PORT" {
  export -n LDAP_PORT
  run query_pg_ldap_sync ".ldap_connection.port"
  assert_output "389"
}

@test "Test setting LDAP_USER_BASE_DN" {
  export LDAP_USER_BASE_DN="OU=users,DC=example,DC=com"
  run query_pg_ldap_sync ".ldap_users.base"
  export -n LDAP_USER_BASE_DN
  assert_output "OU=users,DC=example,DC=com"
}

@test "Test setting LDAP_USER_FILTER" {
  export LDAP_USER_FILTER="(objectClass=posixAccount)"
  run query_pg_ldap_sync ".ldap_users.filter"
  export -n LDAP_USER_FILTER
  assert_output "(objectClass=posixAccount)"
}

@test "Test setting LDAP_USER_NAME_ATTR" {
  export LDAP_USER_NAME_ATTR="samAccountName"
  run query_pg_ldap_sync ".ldap_users.name_attribute"
  export -n LDAP_USER_NAME_ATTR
  assert_output "samAccountName"
}

@test "Test default LDAP_USER_NAME_ATTR" {
  export -n LDAP_USER_NAME_ATTR
  run query_pg_ldap_sync  ".ldap_users.name_attribute"
  assert_output "userPrincipalName"
}

@test "Test setting POSTGRESQL_DB_NAME" {
  export POSTGRESQL_DB_NAME="custom-db-name"
  run query_pg_ldap_sync ".pg_connection.dbname"
  export -n POSTGRESQL_DB_NAME
  assert_output "custom-db-name"
}

@test "Test default POSTGRESQL_DB_NAME" {
  export -n POSTGRESQL_DB_NAME
  run query_pg_ldap_sync ".pg_connection.dbname"
  export -n POSTGRESQL_DB_NAME
  assert_output "guacamole"
}

@test "Test setting POSTGRESQL_HOST" {
  export POSTGRESQL_HOST="postgresql.example.com"
  run query_pg_ldap_sync ".pg_connection.host"
  export -n POSTGRESQL_HOST
  assert_output "postgresql.example.com"
}

@test "Test setting POSTGRESQL_PASSWORD" {
  export POSTGRESQL_PASSWORD="!a#b%c"
  run query_pg_ldap_sync ".pg_connection.password"
  export -n POSTGRESQL_PASSWORD
  assert_output "!a#b%c"
}

@test "Test setting POSTGRESQL_PORT" {
  export POSTGRESQL_PORT="1234"
  run query_pg_ldap_sync ".pg_connection.port"
  export -n POSTGRESQL_PORT
  assert_output "1234"
}

@test "Test default POSTGRESQL_PORT" {
  export -n POSTGRESQL_PORT
  run query_pg_ldap_sync ".pg_connection.port"
  assert_output "5432"
}

@test "Test setting POSTGRESQL_USERNAME" {
  export POSTGRESQL_USERNAME="psqladmin"
  run query_pg_ldap_sync ".pg_connection.user"
  export -n POSTGRESQL_USERNAME
  assert_output "psqladmin"
}
