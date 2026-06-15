"""
auth/models.py — SQLAlchemy User model 
"""
from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

AUTH_DB_URL = os.getenv("AUTH_DB_URL", "sqlite:///./auth.db")

engine         = create_engine(AUTH_DB_URL, connect_args={"check_same_thread": False})
SessionLocal   = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(80), unique=True, index=True, nullable=False)
    email           = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(String(10), nullable=False, default="user")  # "admin" | "user"


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()