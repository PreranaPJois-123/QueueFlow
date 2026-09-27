"""Privileged CLI, run with trusted database access; no public role escalation."""
import argparse
import os
from getpass import getpass

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.models import User, UserRole
from app.schemas.schemas import UserRegister


def bootstrap_admin_from_env():
    """Provision the first admin once, using private deployment environment variables.

    Never changes an existing account or password. An operator must supply all
    three variables; public registration cannot grant privileged roles.
    """
    keys = ("INITIAL_ADMIN_EMAIL", "INITIAL_ADMIN_NAME", "INITIAL_ADMIN_PASSWORD")
    values = [os.environ.get(key, "").strip() for key in keys]
    if not any(values):
        return
    if not all(values):
        raise ValueError("Set all INITIAL_ADMIN_EMAIL, INITIAL_ADMIN_NAME and INITIAL_ADMIN_PASSWORD")
    payload = UserRegister(email=values[0], full_name=values[1], password=values[2])
    with SessionLocal() as db:
        if db.query(User).filter(User.role == UserRole.ADMIN).first():
            return
        if db.query(User).filter(User.email == payload.email.lower()).first():
            raise ValueError("Initial admin email belongs to an existing account; choose another email")
        db.add(User(email=payload.email.lower(), full_name=payload.full_name,
                    hashed_password=hash_password(payload.password), role=UserRole.ADMIN))
        db.commit()
    print("Initial admin account created")


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
    if os.environ.get("QUEUEFLOW_BOOTSTRAP_ADMIN") == "1":
        bootstrap_admin_from_env()
    else:
        main()
