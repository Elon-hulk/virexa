from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, unique=True, index=True)
    username = Column(String)
    avatar = Column(String, nullable=True)
    access_token = Column(String)
    refresh_token = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    discord_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, unique=True, index=True)
    log_channel_id = Column(String, nullable=True)
    prefix = Column(String, default="/")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    events = relationship("Event", back_populates="server")
    logs = relationship("Log", back_populates="server")

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, ForeignKey("servers.guild_id"))
    event_name = Column(String)
    enabled = Column(Boolean, default=False)

    server = relationship("Server", back_populates="events")

class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, ForeignKey("servers.guild_id"))
    event_type = Column(String)
    user_id = Column(String)
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    server = relationship("Server", back_populates="logs")
