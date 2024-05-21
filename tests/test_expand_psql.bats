#! /usr/bin/env bats
# bats file_tags=ruby:expand_psql

setup() {
  load 'common'
  common_setup
}

expand_psql() {
  ${TEST_DIR}/../scripts/expand_psql.rb
}

@test "Test setting POSTGRESQL_PASSWORD" {
  export POSTGRESQL_PASSWORD="!a#b%c"
  run expand_psql
  export -n POSTGRESQL_PASSWORD
  assert_output --partial "PGPASSWORD='!a#b%c'"
}

@test "Test setting POSTGRESQL_HOST" {
  export POSTGRESQL_HOST="postgresql.example.com"
  run expand_psql
  export -n POSTGRESQL_HOST
  assert_output --partial "-h 'postgresql.example.com'"
}

@test "Test setting POSTGRESQL_PORT" {
  export POSTGRESQL_PORT="1234"
  run expand_psql
  export -n POSTGRESQL_PORT
  assert_output --partial "-p '1234'"
}

@test "Test setting POSTGRESQL_DB_NAME" {
  export POSTGRESQL_DB_NAME="custom-db-name"
  run expand_psql
  export -n POSTGRESQL_DB_NAME
  assert_output --partial "-d 'custom-db-name'"
}

@test "Test setting POSTGRESQL_USERNAME" {
  export POSTGRESQL_USERNAME="postgresqladmin"
  run expand_psql
  export -n POSTGRESQL_USERNAME
  assert_output --partial "-U 'postgresqladmin'"
}
