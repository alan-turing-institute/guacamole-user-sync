import datetime
import logging
import secrets

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine  # type:ignore
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from guacamole_user_sync.models import LDAPGroup, LDAPUser

from .orm import (
    GuacamoleEntity,
    GuacamoleUser,
    GuacamoleUserGroup,
    guacamole_entity_type,
)
from .sql import GuacamoleSchema, SchemaVersion

logger = logging.getLogger("guacamole_user_sync")

LDAPSearchResult = list[tuple[int, tuple[str, dict[str, list[bytes]]]]]


class PostgreSQLClient:
    def __init__(
        self,
        *,
        database_name: str,
        host_name: str,
        port: int,
        user_name: str,
        user_password: str,
    ):
        self.database_name = database_name
        self.host_name = host_name
        self.port = port
        self.user_name = user_name
        self.user_password = user_password
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        if not self._engine:
            url_object = URL.create(
                "postgresql+psycopg",
                username=self.user_name,
                password=self.user_password,
                host=self.host_name,
                port=self.port,
                database=self.database_name,
            )
            self._engine = create_engine(url_object, echo=False)
        return self._engine

    def ensure_schema(self, schema_version: SchemaVersion) -> None:
        try:
            with self.engine.begin() as cnxn:
                for command in GuacamoleSchema.commands(schema_version):
                    cnxn.execute(command)
        except OperationalError as exc:
            logger.warning("Unable to connect to the PostgreSQL server.")
            raise PostgreSQLException from exc

    def update(self, *, groups: list[LDAPGroup], users: list[LDAPUser]) -> None:
        self.update_groups(groups)
        self.update_users(users)
        self.update_group_entities()
        self.update_user_entities(users)

    def update_groups(self, groups: list[LDAPGroup]) -> None:
        """Update the entities table with desired groups"""
        with Session(self.engine) as session:  # type:ignore
            # Set groups to desired list
            logger.info(f"Ensuring that {len(groups)} group(s) are registered")
            desired_group_names = [group.name for group in groups]
            current_group_names = [
                group.name
                for group in session.query(GuacamoleEntity).filter_by(
                    type=guacamole_entity_type.USER_GROUP
                )
            ]
            # Add groups
            logger.info(
                f"There are {len(current_group_names)} group(s) currently registered"
            )
            group_names_to_add = [
                group_name
                for group_name in desired_group_names
                if group_name not in current_group_names
            ]
            logger.info(f"... {len(group_names_to_add)} group(s) will be added")
            session.add_all(
                [
                    GuacamoleEntity(
                        name=group_name, type=guacamole_entity_type.USER_GROUP
                    )
                    for group_name in group_names_to_add
                ]
            )
            # Remove groups
            group_names_to_remove = [
                group_name
                for group_name in current_group_names
                if group_name not in desired_group_names
            ]
            logger.info(f"... {len(group_names_to_remove)} group(s) will be removed")
            for group_name in group_names_to_remove:
                session.query(GuacamoleEntity).filter(
                    GuacamoleEntity.name == group_name,
                    GuacamoleEntity.type == guacamole_entity_type.USER_GROUP,
                ).delete()
            session.commit()

    def update_group_entities(self) -> None:
        """Add group entities to the groups table"""
        with Session(self.engine) as session:  # type:ignore
            current_user_group_entity_ids = [
                group.entity_id for group in session.query(GuacamoleUserGroup)
            ]
            logger.info(
                f"There are {len(current_user_group_entity_ids)}"
                " user group entit(y|ies) currently registered"
            )
            new_group_entity_ids = [
                group.entity_id
                for group in session.query(GuacamoleEntity).filter_by(
                    type=guacamole_entity_type.USER_GROUP
                )
                if group.entity_id not in current_user_group_entity_ids
            ]
            logger.info(
                f"... {len(new_group_entity_ids)} user group entit(y|ies) will be added"
            )
            session.add_all(
                [
                    GuacamoleUserGroup(
                        entity_id=group_entity_id,
                    )
                    for group_entity_id in new_group_entity_ids
                ]
            )
            session.commit()

    def update_users(self, users: list[LDAPUser]) -> None:
        """Update the entities table with desired users"""
        with Session(self.engine) as session:  # type:ignore
            # Set users to desired list
            logger.info(f"Ensuring that {len(users)} user(s) are registered")
            desired_usernames = [user.name for user in users]
            current_usernames = [
                user.name
                for user in session.query(GuacamoleEntity).filter_by(
                    type=guacamole_entity_type.USER
                )
            ]
            # Add users
            logger.info(
                f"There are {len(current_usernames)} user(s) currently registered"
            )
            usernames_to_add = [
                username
                for username in desired_usernames
                if username not in current_usernames
            ]
            logger.info(f"... {len(usernames_to_add)} user(s) will be added")
            session.add_all(
                [
                    GuacamoleEntity(name=username, type=guacamole_entity_type.USER)
                    for username in usernames_to_add
                ]
            )
            # Remove users
            usernames_to_remove = [
                username
                for username in current_usernames
                if username not in desired_usernames
            ]
            logger.info(f"... {len(usernames_to_remove)} user(s) will be removed")
            for username in usernames_to_remove:
                session.query(GuacamoleEntity).filter(
                    GuacamoleEntity.name == username,
                    GuacamoleEntity.type == guacamole_entity_type.USER,
                ).delete()
            session.commit()

    def update_user_entities(self, users: list[LDAPUser]) -> None:
        """Add user entities to the users table"""
        with Session(self.engine) as session:  # type:ignore
            current_user_entity_ids = [
                user.entity_id for user in session.query(GuacamoleUser)
            ]
            logger.info(
                f"There are {len(current_user_entity_ids)} "
                "user entit(y|ies) currently registered"
            )
            new_user_tuples: list[tuple[int, LDAPUser]] = [
                (user.entity_id, [u for u in users if u.name == user.name][0])
                for user in session.query(GuacamoleEntity).filter_by(
                    type=guacamole_entity_type.USER
                )
                if user.entity_id not in current_user_entity_ids
            ]
            logger.info(
                f"... {len(current_user_entity_ids)} user entit(y|ies) will be added"
            )
            session.add_all(
                [
                    GuacamoleUser(
                        entity_id=user_tuple[0],
                        full_name=user_tuple[1].display_name,
                        password_date=datetime.datetime.now(),
                        password_hash=secrets.token_bytes(32),
                        password_salt=secrets.token_bytes(32),
                    )
                    for user_tuple in new_user_tuples
                ]
            )
            session.commit()
