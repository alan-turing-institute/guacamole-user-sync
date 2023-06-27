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
    WHERE (groname LIKE 'SG %')
ON CONFLICT DO NOTHING;

/* Ensure that all user groups are Guacamole user groups */
INSERT INTO guacamole_user_group (entity_id)
SELECT entity_id
FROM
    guacamole_entity WHERE type = 'USER_GROUP'
ON CONFLICT DO NOTHING;

/* Ensure that all users are added to the correct group */
DELETE FROM guacamole_user_group_member;
INSERT INTO guacamole_user_group_member (user_group_id, member_entity_id)
SELECT guacamole_user_group.user_group_id, guac_user.entity_id
FROM
    pg_group
    JOIN pg_user ON pg_has_role(pg_user.usesysid, grosysid, 'member')
    JOIN guacamole_entity guac_group ON pg_group.groname = guac_group.name
    JOIN guacamole_entity guac_user ON pg_user.usename = guac_user.name
    JOIN guacamole_user_group ON guacamole_user_group.entity_id = guac_group.entity_id
    WHERE (groname LIKE 'SG %')
ON CONFLICT DO NOTHING;

/* Grant administration permissions to members of the System Administrators group */
INSERT INTO guacamole_system_permission (entity_id, permission)
SELECT entity_id, permission :: guacamole_system_permission_type
FROM
    (
        VALUES
            ('{{ADMINISTRATORS_GROUP_NAME}}', 'CREATE_CONNECTION'),
            ('{{ADMINISTRATORS_GROUP_NAME}}', 'CREATE_CONNECTION_GROUP'),
            ('{{ADMINISTRATORS_GROUP_NAME}}', 'CREATE_SHARING_PROFILE'),
            ('{{ADMINISTRATORS_GROUP_NAME}}', 'CREATE_USER'),
            ('{{ADMINISTRATORS_GROUP_NAME}}', 'CREATE_USER_GROUP'),
            ('{{ADMINISTRATORS_GROUP_NAME}}', 'ADMINISTER')
    ) group_permissions (username, permission)
    JOIN guacamole_entity ON group_permissions.username = guacamole_entity.name AND guacamole_entity.type = 'USER_GROUP'
ON CONFLICT DO NOTHING;

/* Assign connection permissions to each group */
DELETE FROM guacamole_connection_permission;
INSERT INTO guacamole_connection_permission (entity_id, connection_id, permission)
    SELECT entity_id, connection_id, permission::guacamole_object_permission_type
    FROM
        (
            VALUES
                ('{{ADMINISTRATORS_GROUP_NAME}}', 'READ'),
                ('{{ADMINISTRATORS_GROUP_NAME}}', 'UPDATE'),
                ('{{ADMINISTRATORS_GROUP_NAME}}', 'DELETE'),
                ('{{ADMINISTRATORS_GROUP_NAME}}', 'ADMINISTER'),
                ('{{USERS_GROUP_NAME}}', 'READ')
        ) group_permissions (username, permission)
        CROSS JOIN guacamole_connection
        JOIN guacamole_entity ON group_permissions.username = guacamole_entity.name
ON CONFLICT DO NOTHING;

/* Remove the default guacadmin user */
DELETE FROM guacamole_entity WHERE guacamole_entity.name = 'guacadmin';
