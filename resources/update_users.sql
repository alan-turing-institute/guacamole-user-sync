/* Ensure that the 'ldap_users' group exists */
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles
        WHERE rolname = 'ldap_users'
    ) THEN
        CREATE ROLE ldap_users;
    END IF;
END $$;

/* Ensure that the 'ldap_groups' group exists */
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles
        WHERE rolname = 'ldap_groups'
    ) THEN
        CREATE ROLE ldap_groups;
    END IF;
END $$;

/* Ensure that all LDAP users are Guacamole entities */
INSERT INTO guacamole_entity (name, type)
SELECT usename, 'USER'
FROM
    pg_user
    JOIN pg_auth_members ON (pg_user.usesysid = pg_auth_members.member)
    JOIN pg_roles ON (pg_roles.oid = pg_auth_members.roleid)
    WHERE rolname = 'ldap_users'
ON CONFLICT DO NOTHING;

/* Ensure that all LDAP users are Guacamole users */
INSERT INTO guacamole_user (entity_id, password_hash, password_salt, password_date)
SELECT entity_id, password_hash, password_salt, CURRENT_TIMESTAMP as password_date
FROM
    (
        SELECT
            usename,
            decode(md5(random() :: text), 'hex'),
            decode(md5(random() :: text), 'hex')
        FROM
        pg_user
        JOIN pg_auth_members ON (pg_user.usesysid = pg_auth_members.member)
        JOIN pg_roles ON (pg_roles.oid = pg_auth_members.roleid)
        WHERE rolname = 'ldap_users'
    ) user_details (username, password_hash, password_salt)
    JOIN guacamole_entity ON user_details.username = guacamole_entity.name
ON CONFLICT DO NOTHING;

/* Ensure that all user groups are Guacamole entities */
INSERT INTO guacamole_entity (name, type)
SELECT groname, 'USER_GROUP'
FROM
    pg_group
    WHERE groname NOT LIKE '%pg_%' and groname NOT LIKE 'ldap_%'
ON CONFLICT DO NOTHING;

/* Ensure that all user groups are Guacamole user groups */
INSERT INTO guacamole_user_group (entity_id)
SELECT entity_id
FROM
    guacamole_entity WHERE type = 'USER_GROUP'
ON CONFLICT DO NOTHING;

/* Assign all users to the correct groups */
-- DELETE FROM guacamole_user_group_member;
INSERT INTO guacamole_user_group_member (user_group_id, member_entity_id)
SELECT guacamole_user_group.user_group_id, guac_user.entity_id
FROM
    pg_group
    JOIN pg_user ON pg_has_role(pg_user.usesysid, grosysid, 'member')
    JOIN guacamole_entity guac_group ON pg_group.groname = guac_group.name
    JOIN guacamole_entity guac_user ON pg_user.usename = guac_user.name
    JOIN guacamole_user_group ON guacamole_user_group.entity_id = guac_group.entity_id
ON CONFLICT DO NOTHING;
