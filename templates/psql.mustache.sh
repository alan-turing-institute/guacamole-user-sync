#! /bin/bash

# Run database initialisation so that the desired tables exist
psql "host={{{POSTGRESQL_HOST}}} port={{{POSTGRESQL_PORT}}} dbname={{{POSTGRESQL_DB_NAME}}} user={{{POSTGRESQL_USERNAME}}} password={{{POSTGRESQL_PASSWORD}}} sslmode=require" -f /app/resources/init_db.sql

# Run LDAP synchronisation
psql "host={{{POSTGRESQL_HOST}}} port={{{POSTGRESQL_PORT}}} dbname={{{POSTGRESQL_DB_NAME}}} user={{{POSTGRESQL_USERNAME}}} password={{{POSTGRESQL_PASSWORD}}} sslmode=require" -f /app/resources/update_users.sql
