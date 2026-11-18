#!/usr/bin/env python
"""Administer users from the server shell (this API has no public sign-up).

    python manage_users.py create alice --role user      # prompts for the password
    python manage_users.py list
    python manage_users.py deactivate alice
    python manage_users.py passwd alice
"""
import argparse
import getpass
import sys

from app.db import init_db
from app.services import user_service


def _pw() -> str:
    a, b = getpass.getpass("Password (min 10 chars): "), getpass.getpass("Repeat: ")
    if a != b:
        sys.exit("Passwords do not match")
    return a


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("username"); c.add_argument("--role", choices=["user", "admin"], default="user")
    sub.add_parser("list")
    d = sub.add_parser("deactivate"); d.add_argument("username")
    r = sub.add_parser("passwd"); r.add_argument("username")
    a = p.parse_args()
    init_db()
    try:
        if a.cmd == "create":
            u = user_service.create_user(a.username, _pw(), a.role); print("created", u["username"], u["role"])
        elif a.cmd == "list":
            for u in user_service.list_users():
                print(f'{u["id"]:>3}  {u["username"]:<24} {u["role"]:<6} {"active" if u["is_active"] else "DISABLED"}')
        elif a.cmd == "deactivate":
            print("deactivated" if user_service.set_active(a.username, False) else "no such user")
        elif a.cmd == "passwd":
            print("updated" if user_service.set_password(a.username, _pw()) else "no such user")
    except ValueError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
