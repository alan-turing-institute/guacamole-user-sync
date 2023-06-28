#! /bin/bash

# Run LDAP synchronisation
psql "host={{POSTGRES_HOST}} port={{POSTGRES_PORT}} dbname={{POSTGRES_DB_NAME}} user={{POSTGRES_USERNAME}} password={{POSTGRES_PASSWORD}} sslmode=require" -f /app/resources/update_users.sql

