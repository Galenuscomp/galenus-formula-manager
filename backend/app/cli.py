"""Admin commands.

  python -m app.cli migrate
  python -m app.cli create-user --email a@b.c --name "Full Name" --role admin
"""

import argparse
import getpass
import sys
from pathlib import Path

from sqlalchemy import select


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    command.upgrade(cfg, "head")


def create_user(email: str, name: str, role: str, licence: str | None) -> None:
    from app.db import session_factory
    from app.models import User
    from app.security import ROLES, hash_password

    if role not in ROLES:
        sys.exit(f"role must be one of {ROLES}")
    password = getpass.getpass("Password (min 10 chars): ")
    if len(password) < 10 or password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords must match and be at least 10 characters")
    with session_factory()() as db:
        if db.scalar(select(User).where(User.email == email.lower())):
            sys.exit("User already exists")
        db.add(User(email=email.lower(), full_name=name, role=role, licence_number=licence,
                    password_hash=hash_password(password)))
        db.commit()
    print(f"Created {role} {email}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    cu = sub.add_parser("create-user")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", required=True)
    cu.add_argument("--licence")
    args = parser.parse_args()
    if args.cmd == "migrate":
        migrate()
    else:
        create_user(args.email, args.name, args.role, args.licence)


if __name__ == "__main__":
    main()
