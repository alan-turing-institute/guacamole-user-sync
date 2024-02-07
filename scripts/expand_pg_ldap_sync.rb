#! /usr/bin/env ruby

require 'mustache'

# Provide mustache arguments from environment variables
Mustache.template_file = File.dirname(__FILE__) + "/../templates/pg_ldap_sync.mustache.yaml"
view = Mustache.new
view[:LDAP_BIND_DN] = ENV["LDAP_BIND_DN"]
view[:LDAP_BIND_PASSWORD] = ENV["LDAP_BIND_PASSWORD"]
view[:LDAP_GROUP_BASE_DN] = ENV["LDAP_GROUP_BASE_DN"]
view[:LDAP_GROUP_FILTER] = ENV["LDAP_GROUP_FILTER"]
view[:LDAP_HOST] = ENV["LDAP_HOST"]
view[:LDAP_USER_BASE_DN] = ENV["LDAP_USER_BASE_DN"]
view[:LDAP_USER_FILTER] = ENV["LDAP_USER_FILTER"]
view[:POSTGRESQL_DB_NAME] = ENV["POSTGRESQL_DB_NAME"] || "guacamole"
view[:POSTGRESQL_HOST] = ENV["POSTGRESQL_HOST"]
view[:POSTGRESQL_PASSWORD] = ENV["POSTGRESQL_PASSWORD"]
view[:POSTGRESQL_USERNAME] = ENV["POSTGRESQL_USERNAME"]

# Write the expanded template to stdout
puts view.render
