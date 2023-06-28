#! /bin/bash

# Expand mustache template
echo "$(date -I"seconds") Expanding mustache templates..."
/app/scripts/expand_pg_ldap_sync.rb > /app/resources/pg-ldap-sync.yaml
chmod 0600 /app/resources/pg-ldap-sync.yaml
/app/scripts/expand_psql.rb > /app/scripts/psql.sh
chmod 0700 /app/scripts/psql.sh

# Run LDAP synchronisation
echo "$(date -I"seconds") Running LDAP synchronisation..."
/usr/local/bin/pg_ldap_sync -vvv -c /app/resources/pg-ldap-sync.yaml 2>&1
echo "$(date -I"seconds") Updating database..."
/app/scripts/psql.sh
echo "$(date -I"seconds") Finished database synchronisation"
