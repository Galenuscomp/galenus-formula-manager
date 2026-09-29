"""Admin commands.

  python -m app.cli migrate
  python -m app.cli create-user --email a@b.c --name "Full Name" --role admin
  python -m app.cli password-link --email a@b.c   # one-time link to choose a new password
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
    from app.security import ROLES, hash_password, password_problems

    if role not in ROLES:
        sys.exit(f"role must be one of {ROLES}")
    password = getpass.getpass("Password (min 10 characters, a letter and a digit): ")
    problems = password_problems(password, email)
    if problems:
        sys.exit(" ".join(problems))
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match")
    with session_factory()() as db:
        if db.scalar(select(User).where(User.email == email.lower())):
            sys.exit("User already exists")
        db.add(User(email=email.lower(), full_name=name, role=role, licence_number=licence,
                    password_hash=hash_password(password)))
        db.commit()
    print(f"Created {role} {email}")


def password_link(email: str) -> None:
    """For a locked-out admin: prints a link instead of asking for a password in
    the console, where some keyboard layouts garble special characters."""
    from app import passwords
    from app.config import get_settings
    from app.db import session_factory
    from app.models import User

    with session_factory()() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        if user is None or not user.is_active:
            sys.exit("No active user with that e-mail")
        link = passwords.issue_link(db, user, None)
        db.commit()
    origin = (get_settings().public_origin or "").rstrip("/")
    print(f"Open within {'3 days' if link['purpose'] == 'invite' else '24 hours'}: {origin}{link['path']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    cu = sub.add_parser("create-user")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", required=True)
    cu.add_argument("--licence")
    pl = sub.add_parser("password-link")
    pl.add_argument("--email", required=True)
    args = parser.parse_args()
    if args.cmd == "migrate":
        migrate()
    elif args.cmd == "password-link":
        password_link(args.email)
    else:
        create_user(args.email, args.name, args.role, args.licence)


if __name__ == "__main__":
    main()
