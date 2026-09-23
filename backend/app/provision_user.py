"""Privileged CLI, run with trusted database access; no public role escalation."""
import argparse
from getpass import getpass

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.models import User, UserRole
from app.schemas.schemas import UserRegister


def main():
    parser = argparse.ArgumentParser(description="Create a staff/admin account (never overwrites an existing user)")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=["STAFF", "ADMIN"], default="STAFF")
    args = parser.parse_args()
    password = getpass("New account password: ")
    if password != getpass("Repeat password: "):
        parser.error("Passwords do not match")
    payload = UserRegister(email=args.email, full_name=args.name, password=password)
    with SessionLocal() as db:
        if db.query(User).filter(User.email == payload.email.lower()).first():
            parser.error("Account already exists; no changes made")
        db.add(User(email=payload.email.lower(), full_name=payload.full_name,
                    hashed_password=hash_password(payload.password), role=UserRole(args.role)))
        db.commit()
    print("Account created")


if __name__ == "__main__":
    main()
