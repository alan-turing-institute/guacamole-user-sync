import logging
import secrets
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

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
from .postgresql_backend import PostgreSQLBackend, PostgreSQLConnectionDetails
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
            connection_details=PostgreSQLConnectionDetails(
                database_name=database_name,
                host_name=host_name,
                port=port,
                user_name=user_name,
                user_password=user_password,
            ),
        )

    def assign_users_to_groups(
        self,
        groups: list[LDAPGroup],
        users: list[LDAPUser],
    ) -> None:
        logger.info(
            "Ensuring that %s user(s) are correctly assigned among %s group(s)",
            len(users),
            len(groups),
        )
        user_group_members = []
        for group in groups:
            logger.debug("Working on group '%s'", group.name)
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
                    "-> entity_id: %s; user_group_id: %s",
                    group_entity_id,
                    user_group_id,
                )
            except IndexError:
                logger.debug(
                    "Could not determine user_group_id for group '%s'.",
                    group.name,
                )
                continue
            # Get the user_entity_id for each user belonging to this group
            for user_uid in group.member_uid:
                try:
                    user = next(filter(lambda u: u.uid == user_uid, users))
                except StopIteration:
                    logger.debug("Could not find LDAP user with UID %s", user_uid)
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
                        "... group member '%s' has entity_id '%s'",
                        user,
                        user_entity_id,
                    )
                except IndexError:
                    logger.debug(
                        "Could not find entity ID for LDAP user '%s'",
                        user_uid,
                    )
                    continue
                # Create an entry in the user group member table
                user_group_members.append(
                    GuacamoleUserGroupMember(
                        user_group_id=user_group_id,
                        member_entity_id=user_entity_id,
                    ),
                )
        # Clear existing assignments then reassign
        logger.debug(
            "... creating %s user/group assignments.",
            len(user_group_members),
        )
        self.backend.delete(GuacamoleUserGroupMember)
        self.backend.add_all(user_group_members)

    def ensure_schema(self, schema_version: SchemaVersion) -> None:
        try:
            self.backend.execute_commands(GuacamoleSchema.commands(schema_version))
        except SQLAlchemyError as exc:
            msg = "Unable to ensure PostgreSQL schema."
            raise PostgreSQLError(msg) from exc

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
        logger.info("Ensuring that %s group(s) are registered", len(groups))
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
            "There are %s group(s) currently registered",
            len(current_group_names),
        )
        group_names_to_add = [
            group_name
            for group_name in desired_group_names
            if group_name not in current_group_names
        ]
        logger.debug("... %s group(s) will be added", len(group_names_to_add))
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
        logger.debug("... %s group(s) will be removed", len(group_names_to_remove))
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
            "There are %s user group entit(y|ies) currently registered",
            len(current_user_group_entity_ids),
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
            "... %s user group entit(y|ies) will be added",
            len(new_group_entity_ids),
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
        logger.debug(
            "There are %s valid user group entit(y|ies)",
            len(valid_entity_ids),
        )
        self.backend.delete(
            GuacamoleUserGroup,
            GuacamoleUserGroup.entity_id.not_in(valid_entity_ids),
        )

    def update_users(self, users: list[LDAPUser]) -> None:
        """Update the entities table with desired users."""
        # Set users to desired list
        logger.info("Ensuring that %s user(s) are registered", len(users))
        desired_usernames = [user.name for user in users]
        current_usernames = [
            user.name
            for user in self.backend.query(
                GuacamoleEntity,
                type=GuacamoleEntityType.USER,
            )
        ]
        # Add users
        logger.debug(
            "There are %s user(s) currently registered",
            len(current_usernames),
        )
        usernames_to_add = [
            username
            for username in desired_usernames
            if username not in current_usernames
        ]
        logger.debug("... %s user(s) will be added", len(usernames_to_add))
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
        logger.debug("... %s user(s) will be removed", len(usernames_to_remove))
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
            "There are %s user entit(y|ies) currently registered",
            len(current_user_entity_ids),
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
            "... %s user entit(y|ies) will be added",
            len(current_user_entity_ids),
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
        logger.debug("There are %s valid user entit(y|ies)", len(valid_entity_ids))
        self.backend.delete(
            GuacamoleUser,
            GuacamoleUser.entity_id.not_in(valid_entity_ids),
        )
