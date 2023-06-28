#! /bin/bash

# Run database initialisation so that the desired tables exist
psql "host={{POSTGRES_HOST}} port={{POSTGRES_PORT}} dbname={{POSTGRES_DB_NAME}} user={{POSTGRES_USERNAME}} password={{POSTGRES_PASSWORD}} sslmode=require" -f /app/resources/init_db.sql

# Run LDAP synchronisation
psql "host={{POSTGRES_HOST}} port={{POSTGRES_PORT}} dbname={{POSTGRES_DB_NAME}} user={{POSTGRES_USERNAME}} password={{POSTGRES_PASSWORD}} sslmode=require" -f /app/resources/update_users.sql

