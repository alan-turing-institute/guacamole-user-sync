#! /bin/bash

# Run database initialisation so that the desired tables exist
export PGPASSWORD='{{{POSTGRESQL_PASSWORD}}}'; psql -h '{{{POSTGRESQL_HOST}}}' -p '{{{POSTGRESQL_PORT}}}' -d '{{{POSTGRESQL_DB_NAME}}}' -U '{{{POSTGRESQL_USERNAME}}}' --set=sslmode=require -f /app/resources/init_db.sql

# Run LDAP synchronisation
export PGPASSWORD='{{{POSTGRESQL_PASSWORD}}}'; psql -h '{{{POSTGRESQL_HOST}}}' -p '{{{POSTGRESQL_PORT}}}' -d '{{{POSTGRESQL_DB_NAME}}}' -U '{{{POSTGRESQL_USERNAME}}}' --set=sslmode=require -f /app/resources/update_users.sql
