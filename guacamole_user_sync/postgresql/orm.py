import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, LargeBinary, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GuacamoleEntityType(enum.Enum):
    """Guacamole entity enum."""

    USER = "USER"
    USER_GROUP = "USER_GROUP"


class GuacamoleObjectPermissionType(enum.Enum):
    """Guacamole object permission enum."""

    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ADMINISTER = "ADMINISTER"


def parse_group_permissions(
    value: str,
) -> dict[str, list[GuacamoleObjectPermissionType]]:
    """Parse `name=PERM,PERM;name=PERM` into a group-name -> permissions map."""
    group_permissions: dict[str, list[GuacamoleObjectPermissionType]] = {}
    for raw_entry in value.split(";"):
        entry = raw_entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            msg = f"Invalid group permissions entry (missing '='): '{entry}'"
            raise ValueError(msg)

        group_name, permissions_csv = entry.split("=", 1)
        group_name = group_name.strip()
        if not group_name:
            msg = f"Invalid group permissions entry (empty group name): '{entry}'"
            raise ValueError(msg)
        if group_name in group_permissions:
            msg = f"Duplicate group name in group permissions: '{group_name}'"
            raise ValueError(msg)

        permissions: list[GuacamoleObjectPermissionType] = []
        for raw_permission_name in permissions_csv.split(","):
            permission_name = raw_permission_name.strip().upper()
            if not permission_name:
                continue
            try:
                permissions.append(GuacamoleObjectPermissionType[permission_name])
            except KeyError:
                msg = (
                    f"Invalid permission '{permission_name}' for group "
                    f"'{group_name}'"
                )
                raise ValueError(msg) from None
        group_permissions[group_name] = permissions
    return group_permissions


class GuacamoleBase(DeclarativeBase):  # type: ignore[misc]
    """Guacamole database base table."""


class GuacamoleEntity(GuacamoleBase):
    """Guacamole database GuacamoleEntity table."""

    __tablename__ = "guacamole_entity"

    entity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    type: Mapped[GuacamoleEntityType] = mapped_column(
        Enum(GuacamoleEntityType, name="guacamole_entity_type"),
    )


class GuacamoleUser(GuacamoleBase):
    """Guacamole database GuacamoleUser table."""

    __tablename__ = "guacamole_user"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(Integer)
    full_name: Mapped[str] = mapped_column(String(256))
    password_hash: Mapped[bytes] = mapped_column(LargeBinary)
    password_salt: Mapped[bytes] = mapped_column(LargeBinary)
    password_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GuacamoleUserGroup(GuacamoleBase):
    """Guacamole database GuacamoleUserGroup table."""

    __tablename__ = "guacamole_user_group"

    user_group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(Integer)


class GuacamoleUserGroupMember(GuacamoleBase):
    """Guacamole database GuacamoleUserGroupMember table."""

    __tablename__ = "guacamole_user_group_member"

    user_group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_entity_id: Mapped[int] = mapped_column(Integer)


class GuacamoleConnection(GuacamoleBase):
    """Guacamole database GuacamoleConnection table."""

    __tablename__ = "guacamole_connection"

    connection_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_name: Mapped[str] = mapped_column(String(128))
    protocol: Mapped[str] = mapped_column(String(32))


class GuacamoleConnectionPermission(GuacamoleBase):
    """Guacamole database GuacamoleConnectionPermission table."""

    __tablename__ = "guacamole_connection_permission"

    entity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    permission: Mapped[GuacamoleObjectPermissionType] = mapped_column(
        Enum(GuacamoleObjectPermissionType, name="guacamole_object_permission_type"),
        primary_key=True,
    )
