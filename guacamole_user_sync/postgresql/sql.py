import logging
from enum import StrEnum
from pathlib import Path

import sqlparse
from sqlalchemy import text
from sqlalchemy.sql.expression import TextClause

logger = logging.getLogger("guacamole_user_sync")


class SchemaVersion(StrEnum):
    """Version for Guacamole database schema."""

    v1_5_5 = "1.5.5"


class GuacamoleSchema:
    """Schema for Guacamole database."""

    @classmethod
    def commands(cls, schema_version: SchemaVersion) -> list[TextClause]:
        logger.info(f"Ensuring correct schema for Guacamole {schema_version.value}")
        commands = []
        sql_file_path = Path(__file__).with_name(
            f"guacamole_schema.{schema_version.value}.sql",
        )
        with open(sql_file_path) as f_sql:
            statements = sqlparse.split(f_sql.read())
        for statement in statements:
            # Extract the first comment if there is one
            tokens = sqlparse.parse(statement)[0].tokens
            comment_lines = [
                line.replace("--", "").strip()
                for token in tokens
                for line in str(token).splitlines()
                if isinstance(token, sqlparse.sql.Comment)
            ]
            if first_comment := next(filter(lambda item: item, comment_lines), None):
                logger.debug(f"... {first_comment}")
            # Extract the command
            commands.append(
                text(sqlparse.format(statement, strip_comments=True, compact=True)),
            )
        return commands
