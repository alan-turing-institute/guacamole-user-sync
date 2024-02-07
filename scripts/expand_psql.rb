#! /usr/bin/env ruby

require 'mustache'

# Provide mustache arguments from environment variables
Mustache.template_file = File.dirname(__FILE__) + "/../templates/psql.mustache.sh"
view = Mustache.new
view[:POSTGRESQL_DB_NAME] = ENV["POSTGRESQL_DB_NAME"] || "guacamole"
view[:POSTGRESQL_HOST] = ENV["POSTGRESQL_HOST"]
view[:POSTGRESQL_PASSWORD] = ENV["POSTGRESQL_PASSWORD"]
view[:POSTGRESQL_PORT] = ENV["POSTGRESQL_PORT"] || "5432"
view[:POSTGRESQL_USERNAME] = ENV["POSTGRESQL_USERNAME"]

# Write the expanded template to stdout
puts view.render
