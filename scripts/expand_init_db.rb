#! /usr/bin/env ruby

require 'mustache'

# Provide mustache arguments from environment variables
Mustache.template_file = File.dirname(__FILE__) + "/../templates/init_db.mustache.sh"
view = Mustache.new
view[:SYSTEM_ADMINISTRATOR_GROUP_NAME] = ENV["SYSTEM_ADMINISTRATOR_GROUP_NAME"] || "System Administrators"

# Write the expanded template to stdout
puts view.render
