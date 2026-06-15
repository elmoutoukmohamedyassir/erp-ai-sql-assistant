"""
auth/auth.py — JWT authentication + role-based authorization
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.models import User

# ── config ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_BEFORE_PRODUCTION_USE")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

Role = Literal["admin", "user"]

# ── password hashing (bcrypt directly — no passlib) ──────────────────────────
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ──────────────────────────────────────────────────────────────────────
class TokenData(BaseModel):
    username: str
    role: Role


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    payload = data.copy()
    expire  = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _decode_token(token: str) -> TokenData:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        role: str | None     = payload.get("role")
        if username is None or role not in ("admin", "user"):
            raise credentials_exc
        return TokenData(username=username, role=role)  # type: ignore[arg-type]
    except JWTError:
        raise credentials_exc


# ── dependency helpers ────────────────────────────────────────────────────────
def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    return _decode_token(token)


def require_admin(current: TokenData = Depends(get_current_user)) -> TokenData:
    if current.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current


def require_any(current: TokenData = Depends(get_current_user)) -> TokenData:
    """Allows both admin and user roles."""
    return current


# ── user helpers ──────────────────────────────────────────────────────────────
def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user