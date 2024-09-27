import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, LargeBinary, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GuacamoleEntityType(enum.Enum):
    """Guacamole entity enum."""

    USER = "USER"
    USER_GROUP = "USER_GROUP"


class GuacamoleBase(DeclarativeBase):  # type: ignore[misc]
    """Guacamole database base table."""


class GuacamoleEntity(GuacamoleBase):
    """Guacamole database GuacamoleEntity table."""

    __tablename__ = "guacamole_entity"

    entity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    type: Mapped[GuacamoleEntityType] = mapped_column(Enum(GuacamoleEntityType, name="guacamole_entity_type"))


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
