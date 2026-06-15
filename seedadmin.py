#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys

from auth.auth import hash_password
from auth.models import User, SessionLocal, create_tables


def seed(username: str, email: str, password: str) -> None:
    create_tables()
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            print(f"[!] User '{username}' already exists — skipping.")
            return

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role="admin",
        )
        db.add(user)
        db.commit()
        print(f"[✓] Admin '{username}' created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the first admin user")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--email",    default="yassir@gmail.com")
    parser.add_argument("--password", default="Yassir")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("[!] Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    seed(args.username, args.email, args.password)