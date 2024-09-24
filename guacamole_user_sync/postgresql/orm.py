import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import (  # type:ignore
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class GuacamoleEntityType(enum.Enum):
    USER = "USER"
    USER_GROUP = "USER_GROUP"


class GuacamoleBase(DeclarativeBase):  # type:ignore
    pass


class GuacamoleEntity(GuacamoleBase):
    __tablename__ = "guacamole_entity"

    entity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    type: Mapped[GuacamoleEntityType] = mapped_column(Enum(GuacamoleEntityType))


class GuacamoleUser(GuacamoleBase):
    __tablename__ = "guacamole_user"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(Integer)
    full_name: Mapped[str] = mapped_column(String(256))
    password_hash: Mapped[bytes] = mapped_column(BYTEA)
    password_salt: Mapped[bytes] = mapped_column(BYTEA)
    password_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GuacamoleUserGroup(GuacamoleBase):
    __tablename__ = "guacamole_user_group"

    user_group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(Integer)


class GuacamoleUserGroupMember(GuacamoleBase):
    __tablename__ = "guacamole_user_group_member"

    user_group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_entity_id: Mapped[int] = mapped_column(Integer)
