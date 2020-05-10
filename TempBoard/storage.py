from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session as _Session
from sqlalchemy.orm import scoped_session, sessionmaker

from .config import Config

_config = Config()
_engine = create_engine(_config.get('storage', 'uri', "sqlite:///./database.sqlite"))

Base = declarative_base(bind=_engine)


def Session() -> _Session:
    return scoped_session(sessionmaker(bind=_engine))()


class Setting(Base):
    __tablename__ = "settings"

    setting_name = Column(String(255), primary_key=True, nullable=True)
    setting_value = Column(String(8000))


class Sensor(Base):
    __tablename__ = "sensors"
    sensor_id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)

    sensor_addr = Column(String(16), nullable=False)
    sensor_name = Column(String(255), nullable=True)


class Reading(Base):
    __tablename__ = "readings"
    reading_id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    reading_date = Column(DateTime, nullable=False)

    sensor_id = Column(Integer, nullable=False)
    sensor_value = Column(Float, nullable=False)
