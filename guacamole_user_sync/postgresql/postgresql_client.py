import logging
import secrets
from datetime import UTC, datetime

from sqlalchemy.exc import OperationalError

from guacamole_user_sync.models import (
    LDAPGroup,
    LDAPUser,
    PostgreSQLError,
)

from .orm import (
    GuacamoleEntity,
    GuacamoleEntityType,
    GuacamoleUser,
    GuacamoleUserGroup,
    GuacamoleUserGroupMember,
)
from .postgresql_backend import PostgreSQLBackend
from .sql import GuacamoleSchema, SchemaVersion

logger = logging.getLogger("guacamole_user_sync")


class PostgreSQLClient:
    """Client for connecting to a PostgreSQL database."""

    def __init__(
        self,
        *,
        database_name: str,
        host_name: str,
        port: int,
        user_name: str,
        user_password: str,
    ) -> None:
        self.backend = PostgreSQLBackend(
            database_name=database_name,
            host_name=host_name,
            port=port,
            user_name=user_name,
            user_password=user_password,
        )

    def assign_users_to_groups(
        self,
        groups: list[LDAPGroup],
        users: list[LDAPUser],
    ) -> None:
        logger.info(
            f"Ensuring that {len(users)} user(s)"
            f" are correctly assigned among {len(groups)} group(s)",
        )
        user_group_members = []
        for group in groups:
            logger.debug(f"Working on group '{group.name}'")
            # Get the user_group_id for each group (via looking up the entity_id)
            try:
                group_entity_id = [
                    item.entity_id
                    for item in self.backend.query(
                        GuacamoleEntity,
                        name=group.name,
                        type=GuacamoleEntityType.USER_GROUP,
                    )
                ][0]
                user_group_id = [
                    item.user_group_id
                    for item in self.backend.query(
                        GuacamoleUserGroup,
                        entity_id=group_entity_id,
                    )
                ][0]
                logger.debug(
                    f"-> entity_id: {group_entity_id}; user_group_id: {user_group_id}",
                )
            except IndexError:
                logger.debug(
                    f"Could not determine user_group_id for group '{group.name}'.",
                )
                continue
            # Get the user_entity_id for each user belonging to this group
            for user_uid in group.member_uid:
                try:
                    user = next(filter(lambda u: u.uid == user_uid, users))
                except StopIteration:
                    logger.debug(f"Could not find LDAP user with UID {user_uid}")
                    continue
                try:
                    user_entity_id = [
                        item.entity_id
                        for item in self.backend.query(
                            GuacamoleEntity,
                            name=user.name,
                            type=GuacamoleEntityType.USER,
                        )
                    ][0]
                    logger.debug(
                        f"... group member '{user}' has entity_id '{user_entity_id}'",
                    )
                except IndexError:
                    logger.debug(f"Could not find entity ID for LDAP user {user_uid}")
                    continue
                # Create an entry in the user group member table
                user_group_members.append(
                    GuacamoleUserGroupMember(
                        user_group_id=user_group_id,
                        member_entity_id=user_entity_id,
                    ),
                )
        # Clear existing assignments then reassign
        logger.debug(f"... creating {len(user_group_members)} user/group assignments.")
        self.backend.delete(GuacamoleUserGroupMember)
        self.backend.add_all(user_group_members)

    def ensure_schema(self, schema_version: SchemaVersion) -> None:
        try:
            self.backend.execute_commands(GuacamoleSchema.commands(schema_version))
        except OperationalError as exc:
            logger.warning("Unable to connect to the PostgreSQL server.")
            raise PostgreSQLError("Unable to ensure PostgreSQL schema.") from exc

    def update(self, *, groups: list[LDAPGroup], users: list[LDAPUser]) -> None:
        """Update the relevant tables to match lists of LDAP users and groups."""
        self.update_groups(groups)
        self.update_users(users)
        self.update_group_entities()
        self.update_user_entities(users)
        self.assign_users_to_groups(groups, users)

    def update_groups(self, groups: list[LDAPGroup]) -> None:
        """Update the entities table with desired groups."""
        # Set groups to desired list
        logger.info(f"Ensuring that {len(groups)} group(s) are registered")
        desired_group_names = [group.name for group in groups]
        current_group_names = [
            item.name
            for item in self.backend.query(
                GuacamoleEntity,
                type=GuacamoleEntityType.USER_GROUP,
            )
        ]
        # Add groups
        logger.debug(
            f"There are {len(current_group_names)} group(s) currently registered",
        )
        group_names_to_add = [
            group_name
            for group_name in desired_group_names
            if group_name not in current_group_names
        ]
        logger.debug(f"... {len(group_names_to_add)} group(s) will be added")
        self.backend.add_all(
            [
                GuacamoleEntity(name=group_name, type=GuacamoleEntityType.USER_GROUP)
                for group_name in group_names_to_add
            ],
        )
        # Remove groups
        group_names_to_remove = [
            group_name
            for group_name in current_group_names
            if group_name not in desired_group_names
        ]
        logger.debug(f"... {len(group_names_to_remove)} group(s) will be removed")
        for group_name in group_names_to_remove:
            self.backend.delete(
                GuacamoleEntity,
                GuacamoleEntity.name == group_name,
                GuacamoleEntity.type == GuacamoleEntityType.USER_GROUP,
            )

    def update_group_entities(self) -> None:
        """Add group entities to the groups table."""
        current_user_group_entity_ids = [
            group.entity_id for group in self.backend.query(GuacamoleUserGroup)
        ]
        logger.debug(
            f"There are {len(current_user_group_entity_ids)}"
            " user group entit(y|ies) currently registered",
        )
        new_group_entity_ids = [
            group.entity_id
            for group in self.backend.query(
                GuacamoleEntity,
                type=GuacamoleEntityType.USER_GROUP,
            )
            if group.entity_id not in current_user_group_entity_ids
        ]
        logger.debug(
            f"... {len(new_group_entity_ids)} user group entit(y|ies) will be added",
        )
        self.backend.add_all(
            [
                GuacamoleUserGroup(
                    entity_id=group_entity_id,
                )
                for group_entity_id in new_group_entity_ids
            ],
        )
        # Clean up any unused entries
        valid_entity_ids = [
            group.entity_id
            for group in self.backend.query(
                GuacamoleEntity,
                type=GuacamoleEntityType.USER_GROUP,
            )
        ]
        logger.debug(f"There are {len(valid_entity_ids)} valid user group entit(y|ies)")
        self.backend.delete(
            GuacamoleUserGroup,
            GuacamoleUserGroup.entity_id.not_in(valid_entity_ids),
        )

    def update_users(self, users: list[LDAPUser]) -> None:
        """Update the entities table with desired users."""
        # Set users to desired list
        logger.info(f"Ensuring that {len(users)} user(s) are registered")
        desired_usernames = [user.name for user in users]
        current_usernames = [
            user.name
            for user in self.backend.query(
                GuacamoleEntity,
                type=GuacamoleEntityType.USER,
            )
        ]
        # Add users
        logger.debug(f"There are {len(current_usernames)} user(s) currently registered")
        usernames_to_add = [
            username
            for username in desired_usernames
            if username not in current_usernames
        ]
        logger.debug(f"... {len(usernames_to_add)} user(s) will be added")
        self.backend.add_all(
            [
                GuacamoleEntity(name=username, type=GuacamoleEntityType.USER)
                for username in usernames_to_add
            ],
        )
        # Remove users
        usernames_to_remove = [
            username
            for username in current_usernames
            if username not in desired_usernames
        ]
        logger.debug(f"... {len(usernames_to_remove)} user(s) will be removed")
        for username in usernames_to_remove:
            self.backend.delete(
                GuacamoleEntity,
                GuacamoleEntity.name == username,
                GuacamoleEntity.type == GuacamoleEntityType.USER,
            )

    def update_user_entities(self, users: list[LDAPUser]) -> None:
        """Add user entities to the users table."""
        current_user_entity_ids = [
            user.entity_id for user in self.backend.query(GuacamoleUser)
        ]
        logger.debug(
            f"There are {len(current_user_entity_ids)} "
            "user entit(y|ies) currently registered",
        )
        new_user_tuples: list[tuple[int, LDAPUser]] = [
            (user.entity_id, [u for u in users if u.name == user.name][0])
            for user in self.backend.query(
                GuacamoleEntity,
                type=GuacamoleEntityType.USER,
            )
            if user.entity_id not in current_user_entity_ids
        ]
        logger.debug(
            f"... {len(current_user_entity_ids)} user entit(y|ies) will be added",
        )
        self.backend.add_all(
            [
                GuacamoleUser(
                    entity_id=user_tuple[0],
                    full_name=user_tuple[1].display_name,
                    password_date=datetime.now(tz=UTC),
                    password_hash=secrets.token_bytes(32),
                    password_salt=secrets.token_bytes(32),
                )
                for user_tuple in new_user_tuples
            ],
        )
        # Clean up any unused entries
        valid_entity_ids = [
            user.entity_id
            for user in self.backend.query(
                GuacamoleEntity,
                type=GuacamoleEntityType.USER,
            )
        ]
        logger.debug(f"There are {len(valid_entity_ids)} valid user entit(y|ies)")
        self.backend.delete(
            GuacamoleUser,
            GuacamoleUser.entity_id.not_in(valid_entity_ids),
        )
