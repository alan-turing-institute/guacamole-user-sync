#! /bin/bash

# Expand mustache template
echo "$(date -I"seconds") Expanding mustache templates..."
/app/scripts/expand_pg_ldap_sync.rb > /app/output/pg-ldap-sync.yaml
/app/scripts/expand_psql.rb > /app/output/psql.sh
/app/scripts/expand_update_users.rb > /app/output/update_users.sql

# Run LDAP synchronisation
echo "$(date -I"seconds") Running LDAP synchronisation..."
/usr/local/bin/pg_ldap_sync -vvv -c /app/output/pg-ldap-sync.yaml 2>&1
echo "$(date -I"seconds") Updating database..."
/app/output/psql.sh
echo "$(date -I"seconds") Finished database synchronisation"
