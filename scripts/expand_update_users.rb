#! /usr/bin/env ruby

require 'mustache'

# Provide mustache arguments from environment variables
Mustache.template_file = File.dirname(__FILE__) + "/../templates/update_users.mustache.sql"
view = Mustache.new
view[:ADMINISTRATORS_GROUP_NAME] = ENV["ADMINISTRATORS_GROUP_NAME"]
view[:LDAP_GROUP_BASE_DN] = ENV["LDAP_GROUP_BASE_DN"]
view[:LDAP_GROUP_FILTER] = ENV["LDAP_GROUP_FILTER"]
view[:POSTGRES_DB_NAME] = ENV["POSTGRES_DB_NAME"] || "guacamole"
view[:POSTGRES_HOST] = ENV["POSTGRES_HOST"]
view[:POSTGRES_PASSWORD] = ENV["POSTGRES_PASSWORD"]
view[:POSTGRES_USERNAME] = ENV["POSTGRES_USERNAME"]
view[:USERS_GROUP_NAME] = ENV["USERS_GROUP_NAME"]

# Write the expanded template to stdout
puts view.render
