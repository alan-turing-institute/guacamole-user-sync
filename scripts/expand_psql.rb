#! /usr/bin/env ruby

require 'mustache'

# Provide mustache arguments from environment variables
Mustache.template_file = File.dirname(__FILE__) + "/../templates/psql.mustache.sh"
view = Mustache.new
view[:POSTGRES_DB_NAME] = ENV["POSTGRES_DB_NAME"] || "guacamole"
view[:POSTGRES_HOST] = ENV["POSTGRES_HOST"]
view[:POSTGRES_PASSWORD] = ENV["POSTGRES_PASSWORD"]
view[:POSTGRES_PORT] = ENV["POSTGRES_PORT"] || "5432"
view[:POSTGRES_USERNAME] = ENV["POSTGRES_USERNAME"]

# Write the expanded template to stdout
puts view.render
