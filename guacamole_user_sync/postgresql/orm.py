import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import (  # type:ignore
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class guacamole_entity_type(enum.Enum):
    USER = "USER"
    USER_GROUP = "USER_GROUP"


class Base(DeclarativeBase):  # type:ignore
    pass


class GuacamoleEntity(Base):
    __tablename__ = "guacamole_entity"

    entity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    type: Mapped[guacamole_entity_type] = mapped_column(Enum(guacamole_entity_type))


class GuacamoleUser(Base):
    __tablename__ = "guacamole_user"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(Integer)
    full_name: Mapped[str] = mapped_column(String(256))
    password_hash: Mapped[bytes] = mapped_column(BYTEA)
    password_salt: Mapped[bytes] = mapped_column(BYTEA)
    password_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GuacamoleUserGroup(Base):
    __tablename__ = "guacamole_user_group"

    user_group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(Integer)
